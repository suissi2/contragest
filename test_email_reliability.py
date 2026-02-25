import unittest
import time
import queue
from unittest.mock import MagicMock, patch
from contragest.core.email_manager import EmailManager
from contragest.core.exceptions import EmailConnectionError

class TestEmailReliability(unittest.TestCase):
    def setUp(self):
        # Reset Singleton for testing
        EmailManager._instance = None
        self.manager = EmailManager()
        
    def test_retry_does_not_block(self):
        """
        Verify that a failing email (scheduled for retry) does not block a subsequent email.
        """
        print("\n--- Testing Non-Blocking Retry ---")
        
        # Mock EmailService to fail on first call for specific recipient, succeed for others
        with patch('contragest.core.email_manager.EmailService') as MockServiceClass:
            mock_service = MockServiceClass.return_value
            mock_service.connect.return_value = MagicMock()
            
            def side_effect_send(server, subject, body, recipient, **kwargs):
                if recipient == "fail@test.com":
                    raise Exception("Simulated Failure")
                print(f"Successfully sent to {recipient}")
                return True
                
            mock_service.send_message.side_effect = side_effect_send

            # 1. Enqueue bad email
            self.manager.enqueue_email("Fail", "Body", "fail@test.com")
            
            # 2. Enqueue good email immediately
            self.manager.enqueue_email("Success", "Body", "success@test.com")
            
            # Wait for processing
            time.sleep(0.5) # Wait less time so retry (2s) is still pending
            
            print(f"Main Queue Size: {self.manager.queue.qsize()}")
            print(f"Retry Queue Size: {self.manager.retry_queue.qsize()}")
            
            # Check where the "fail" email is
            # It should be in retry queue because delay is 2s and we waited 0.5s
            is_in_retry = not self.manager.retry_queue.empty()
            
            # The good email should have been processed
            calls = mock_service.send_message.call_args_list
            recipients = [call[0][3] for call in calls]
            print(f"Sent calls: {recipients}")
            
            self.assertTrue(is_in_retry, "Failed email should be in retry queue (wait was shorter than backoff)")
            self.assertIn("success@test.com", recipients, "Good email should be sent despite initial failure")

if __name__ == '__main__':
    unittest.main()
