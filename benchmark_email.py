import time
import threading
from contragest.core.email_manager import EmailManager
from contragest.core.logging import setup_logger

logger = setup_logger("benchmark")

def run_benchmark(count=10):
    manager = EmailManager()
    
    print(f"--- Starting Email Dispatch Benchmark ({count} emails) ---")
    start_time = time.time()
    
    for i in range(count):
        subject = f"Benchmark Email {i+1}"
        body = f"This is a test email for performance benchmarking. Number: {i+1}"
        recipient = f"test_{i+1}@example.com"
        
        manager.enqueue_email(subject, body, recipient)
    
    enqueue_duration = time.time() - start_time
    print(f"Enqueued {count} emails in {enqueue_duration:.4f}s")
    
    print("Waiting for workers to process... (Check contragest.log for detailed metrics)")
    
    # We can't easily wait for the internal queue to be empty without blocking
    # but we can poll for a bit
    while not manager.queue.empty():
        time.sleep(0.5)
        
    total_duration = time.time() - start_time
    print(f"Approximate total processing time: {total_duration:.2f}s")
    print("Benchmark initiation complete. Verify parallelism in 'contragest.log'.")

if __name__ == "__main__":
    # We use a mocked SMTP for real benchmarking to avoid hitting Planet.tn limits
    # but here we just want to see the queueing logic and worker startup.
    run_benchmark(6)
