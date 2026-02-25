import os
import shutil
from datetime import datetime
from contragest.core.database import DB_PATH

class BackupService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.backup_dir = os.path.join(os.path.dirname(db_path), "backups")

    def create_backup(self) -> str:
        """
        Creates a timestamped backup of the database file using SQLite's backup API.
        This is safer than shutil.copy2 as it handles active transactions better.
        Returns the path to the created backup file.
        """
        if not os.path.exists(self.db_path):
            print(f"Warning: Database file {self.db_path} not found. Backup skipped.")
            return ""

        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_filename = f"contragest_{timestamp}.db"
        backup_path = os.path.join(self.backup_dir, backup_filename)

        import sqlite3
        try:
            # Use SQLite's online backup API
            src = sqlite3.connect(self.db_path)
            dst = sqlite3.connect(backup_path)
            with dst:
                src.backup(dst)
            dst.close()
            src.close()

            print(f"Backup created successfully: {backup_path}")
            self._rotate_backups()
            return backup_path
        except Exception as e:
            print(f"Error creating backup: {e}")
            return ""

    def _rotate_backups(self, keep_last: int = 10):
        """Removes old backups, keeping only the most recent ones."""
        try:
            backups = [os.path.join(self.backup_dir, f) for f in os.listdir(self.backup_dir) if f.endswith(".db")]
            backups.sort(key=os.path.getmtime, reverse=True)

            if len(backups) > keep_last:
                for old_backup in backups[keep_last:]:
                    os.remove(old_backup)
                    print(f"Old backup removed: {old_backup}")
        except Exception as e:
            print(f"Error rotating backups: {e}")

# Global instance for easy use
backup_service = BackupService()
