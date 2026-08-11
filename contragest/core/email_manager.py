import threading
import queue
import time
import smtplib
import socket
import random
from socket import error as socket_error
from datetime import datetime
from typing import Dict, Any, Optional, List
from contragest.core.email_service import EmailService
from contragest.core.logging import setup_logger
from contragest.core.database import SessionLocal, AppConfig
from contragest.core.exceptions import EmailError, EmailConnectionError, EmailAuthenticationError

logger = setup_logger("email_manager")

class EmailManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EmailManager, cls).__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.queue = queue.Queue()
        self.retry_queue = queue.PriorityQueue() # (timestamp, task)
        self.running = True
        self.workers: List[threading.Thread] = []
        self.NUM_WORKERS = 3
        
        for i in range(self.NUM_WORKERS):
            t = threading.Thread(target=self._worker, daemon=True, name=f"EmailWorker-{i}")
            t.start()
            self.workers.append(t)
            
        logger.info(f"EmailManager initialized with {self.NUM_WORKERS} workers.")

    def enqueue_email(self, subject: str, body: str, recipient: str, logo_path: Optional[str] = None):
        """
        Add an email to the sending queue. Returns immediately.
        """
        task = {
            'subject': subject,
            'body': body,
            'recipient': recipient,
            'logo_path': logo_path,
            'timestamp': datetime.now(),
            'queued_at': time.time(), # For latency tracking
            'retries': 0,
            'id': f"{id(subject)}-{int(time.time())}" # Better ID
        }
        self.queue.put(task)
        logger.info(f"Enqueued email to {recipient} (Task ID: {task['id']})")

    def _worker(self):
        """
        Worker loop that manages the SMTP connection and processes the queue.
        Implements Reuse-Connection strategy and Non-Blocking Retry.
        """
        server: Optional[smtplib.SMTP] = None
        last_activity = 0
        CONNECTION_TIMEOUT = 30  # Keep connection open for 30s of idleness
        
        while self.running:
            try:
                # 1. Manage Connection Timeout
                if server and (time.time() - last_activity > CONNECTION_TIMEOUT):
                    try:
                        server.quit()
                    except:
                        pass
                    server = None
                    logger.debug("SMTP connection closed due to inactivity.")

                # 2. Check for Retries
                # If we have items in retry queue that are due, move them to main queue
                while not self.retry_queue.empty():
                    # Peek at the item (timestamp, task)
                    retry_time, task = self.retry_queue.queue[0]
                    if retry_time <= time.time():
                        _, task = self.retry_queue.get()
                        logger.info(f"Moving retry task for {task['recipient']} back to main queue.")
                        self.queue.put(task)
                    else:
                        break # PriorityQueue is sorted, so next items are also in future

                # 3. Get Task (Blocking with timeout to check connection idle & retries)
                try:
                    task = self.queue.get(timeout=1)
                except queue.Empty:
                    continue

                # 4. Process Task
                session = SessionLocal()
                try:
                    config = session.query(AppConfig).first()
                    if not config or not config.smtp_server:
                        logger.error("Skipping email: No SMTP config found.")
                        self.queue.task_done()
                        continue
                    
                    email_service = EmailService(config)

                    # Ensure Connection
                    if server is None:
                        try:
                            server = email_service.connect()
                            logger.info(f"{threading.current_thread().name}: Established new SMTP connection.")
                        except EmailAuthenticationError as e:
                             logger.error(f"Fatal Auth Error: {e}. Dropping email to {task['recipient']}")
                             self.queue.task_done()
                             continue
                        except Exception as e:
                            logger.warning(f"Connection Failed for {task['recipient']}: {e}.")
                            self._handle_retry(task, f"Connect Error: {e}")
                            self.queue.task_done()
                            continue

                    # Send Email
                    try:
                        start_send = time.time()
                        queue_latency = start_send - task['queued_at']
                        
                        email_service.send_message(
                            server, 
                            task['subject'], 
                            task['body'], 
                            task['recipient'],
                            logo_path=task.get('logo_path')
                        )
                        
                        send_duration = time.time() - start_send
                        logger.info(f"Sent email to {task['recipient']} | Queue Latency: {queue_latency:.2f}s | Send Duration: {send_duration:.2f}s")
                        last_activity = time.time()
                    except (smtplib.SMTPServerDisconnected, socket.error, socket_error) as e:
                        logger.warning(f"Connection lost during send to {task['recipient']}: {e}.")
                        server = None # Reconnect next loop
                        self._handle_retry(task, f"Connection/Socket lost: {e}")
                    except Exception as e:
                        logger.error(f"Failed to send email to {task['recipient']} (ID: {task['id']}): {e}", exc_info=True)
                        self._handle_retry(task, str(e))
                    
                finally:
                    session.close()
                    self.queue.task_done()

            except Exception as e:
                 logger.error(f"Unexpected error in email worker: {e}", exc_info=True)
                 time.sleep(1)

        # Cleanup
        if server:
            try:
                server.quit()
            except:
                pass

    def _handle_retry(self, task: Dict[str, Any], reason: str):
        """
        Schedules a task for retry using exponential backoff.
        Drops task if max retries exceeded.
        """
        MAX_RETRIES = 5
        if task['retries'] < MAX_RETRIES:
            task['retries'] += 1
            # Exponential backoff with jitter
            base_delay = 2 ** task['retries']
            jitter = random.uniform(0, 1) * base_delay * 0.5
            delay = base_delay + jitter
            
            future_time = time.time() + delay
            
            logger.info(f"Scheduling retry {task['retries']}/{MAX_RETRIES} for {task['recipient']} in {delay:.1f}s. Reason: {reason}")
            
            # Update queued_at to track latency correctly across retries? 
            # Actually keep original queued_at to see full time from request to success.
            
            # Add to priority queue
            self.retry_queue.put((future_time, task))
        else:
            logger.error(f"Dropped email to {task['recipient']} after {MAX_RETRIES} attempts. Reason: {reason}")
