"""
Machine Connector - Abstraction for communicating with ZK attendance machines.

Uses the `pyzk` library when available, otherwise provides graceful fallbacks
so the UI can still function for configuration management without a physical device.
"""

import socket
import time
import subprocess
import platform
from contragest.core.logging import setup_logger
from contragest.core.error_reporter import ErrorReporter

logger = setup_logger("machine_connector")

# Try importing pyzk (optional dependency)
try:
    from zk import ZK
    PYZK_AVAILABLE = True
except ImportError:
    PYZK_AVAILABLE = False
    logger.warning("pyzk library not installed. Machine communication will be simulated.")


class MachineConnector:
    """Handles communication with a ZK attendance terminal."""

    def __init__(self, default_timeout: int = 10):
        self._conn = None
        self.default_timeout = default_timeout

    # ── Connection ────────────────────────────────────────────────────────

    def test_connection(self, ip: str, port: int = 4370, password: str = "", timeout: int = None) -> tuple:
        """
        Test connectivity to the machine via Ping and TCP.
        Returns (success: bool, message: str).
        """
        tout = timeout or self.default_timeout
        ping_ok = self.ping(ip)
        ping_msg = " [Ping: OK]" if ping_ok else " [Ping: FAILED]"

        if not PYZK_AVAILABLE:
            # Fallback: simple TCP socket probe
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(tout)
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    return True, f"TCP connection to {ip}:{port} succeeded.{ping_msg}"
                else:
                    return False, f"TCP connection to {ip}:{port} refused (code {result}).{ping_msg}"
            except Exception as e:
                return False, f"{str(e)}{ping_msg}"

        try:
            zk = ZK(ip, port=port, timeout=tout, password=int(password) if password else 0)
            conn = zk.connect()
            conn.disconnect()
            return True, f"Successfully connected to ZK device at {ip}:{port}.{ping_msg}"
        except Exception as e:
            return False, f"{str(e)}{ping_msg}"

    def ping(self, ip: str) -> bool:
        """
        Check if the machine responds to ICMP echo requests (Ping).
        """
        # Determine the command flag for count based on OS
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ['ping', param, '1', '-w', '1000', ip] # 1 packet, 1s timeout
        
        try:
            # shell=True on Windows prevents flashing console windows in some contexts,
            # but list arguments are safer. We use creationflags to hide the window if needed.
            startupinfo = None
            if platform.system().lower() == 'windows':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
            return subprocess.call(command, startupinfo=startupinfo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
        except Exception:
            return False

    def connect(self, ip: str, port: int = 4370, password: str = "", timeout: int = None, retries: int = 3):
        """
        Establish a persistent connection to the ZK device with optional retries.
        """
        if not PYZK_AVAILABLE:
            raise RuntimeError("pyzk library is not installed.")
        
        tout = timeout or self.default_timeout
        
        # Pre-flight check: If it's a local address or if we want to fail fast 
        # on unreachable ports without waiting for full ZK timeout logic.
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2) # Fast check
            result = sock.connect_ex((ip, port))
            sock.close()
            if result != 0:
                logger.debug(f"Pre-flight check failed for {ip}:{port} (code {result}). Skipping ZK connection.")
                raise ConnectionRefusedError(f"Port {port} on {ip} is not reachable.")
        except Exception as e:
            logger.debug(f"Pre-flight probe error for {ip}: {e}")
            raise e

        zk = ZK(ip, port=port, timeout=tout, password=int(password) if password else 0)
        
        last_err = None
        for attempt in range(retries):
            try:
                self._conn = zk.connect()
                return self._conn
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    wait = 2 ** attempt
                    logger.debug(f"Connection to {ip} failed (attempt {attempt+1}/{retries}): {e}. Retrying in {wait}s...")
                    time.sleep(wait)
        
        logger.debug(f"Failed to connect to {ip} after {retries} attempts: {last_err}")
        raise last_err

    def disconnect(self):
        if self._conn:
            try:
                self._conn.disconnect()
            except Exception:
                pass
            self._conn = None

    # ── Attendance Data ───────────────────────────────────────────────────

    def get_attendance(self, ip: str, port: int = 4370, password: str = "") -> list:
        """Download all attendance records from the machine."""
        if not PYZK_AVAILABLE:
            logger.warning("pyzk not available - returning empty attendance list.")
            return []
        try:
            conn = self.connect(ip, port, password)
            records = conn.get_attendance()
            self.disconnect()
            return records or []
        except Exception as e:
            logger.debug(f"Error getting attendance from {ip}: {e}")
            self.disconnect()
            return []

    def clear_attendance(self, ip: str, port: int = 4370, password: str = "") -> bool:
        """Clear attendance records on the machine after successful download."""
        if not PYZK_AVAILABLE:
            return False
        try:
            conn = self.connect(ip, port, password)
            conn.clear_attendance()
            self.disconnect()
            return True
        except Exception as e:
            logger.debug(f"Error clearing attendance on {ip}: {e}")
            self.disconnect()
            return False

    # ── Device Inventory & Stats ──────────────────────────────────────────

    def get_device_info(self, ip: str, port: int = 4370, password: str = "") -> dict:
        """Fetch hardware identification details (Serial, Product Name, etc.)."""
        if not PYZK_AVAILABLE:
            return {}
        try:
            conn = self.connect(ip, port, password)
            info = {
                "serial_number": conn.get_serial_number(),
                "product_name": conn.get_device_name(), 
                "device_id": conn.get_device_id(), # Fetch internal Machine Number
                "platform": conn.get_platform(),
                "firmware_version": conn.get_firmware_version(),
                "mac_address": conn.get_mac_address()
            }
            self.disconnect()
            return info
        except Exception as e:
            logger.debug(f"Error getting device info from {ip}: {e}")
            self.disconnect()
            return {}

    def get_device_stats(self, ip: str, port: int = 4370, password: str = "") -> dict:
        """Fetch real-time counters (Users, Fingerprints, Faces).
        
        IMPORTANT: pyzk populates capacity attributes (faces, users_cap, etc.)
        lazily - only after calling get_users() which triggers read_with_buffer()
        that fetches the device storage header block. We MUST call get_users()
        first before reading any capacity attributes.
        """
        if not PYZK_AVAILABLE:
            return {}
        try:
            conn = self.connect(ip, port, password)
            # Trigger lazy attribute population - do NOT remove this call
            users = conn.get_users() or []
            stats = {
                "user_count":        len(users),
                "user_cap":          conn.users_cap  if hasattr(conn, 'users_cap')  and conn.users_cap  else 0,
                "fingerprint_count": conn.fingers    if hasattr(conn, 'fingers')    and conn.fingers    else 0,
                "face_count":        conn.faces      if hasattr(conn, 'faces')      and conn.faces      else 0,
                "face_cap":          conn.faces_cap  if hasattr(conn, 'faces_cap')  and conn.faces_cap  else 0,
            }
            self.disconnect()
            return stats
        except Exception as e:
            logger.debug(f"Error getting device stats from {ip}: {e}")
            self.disconnect()
            return {}

    # ── Time Management ───────────────────────────────────────────────────

    def get_device_time(self, ip: str, port: int = 4370, password: str = "") -> dict:
        """Read the ZK device's current clock time.

        Returns dict with keys:
          success (bool), machine_time (datetime or None),
          message (str), raw_response (str or None).
        """
        if not PYZK_AVAILABLE:
            return {"success": False, "machine_time": None,
                    "message": "pyzk library not installed.", "raw_response": None}
        conn = None
        try:
            conn = self.connect(ip, port, password)
            raw = conn.get_time()
            self.disconnect()
            if raw:
                return {"success": True, "machine_time": raw,
                        "message": f"Machine time: {raw.isoformat()}",
                        "raw_response": raw.isoformat()}
            return {"success": False, "machine_time": None,
                    "message": "Device returned None for get_time().", "raw_response": None}
        except Exception as e:
            if conn:
                try:
                    self.disconnect()
                except Exception:
                    pass
            return {"success": False, "machine_time": None,
                    "message": str(e), "raw_response": None}

    def set_device_time(self, ip: str, port: int = 4370,
                        password: str = "", dt=None) -> dict:
        """Set the ZK device's clock to the given datetime (default: PC now).

        Returns dict with keys:
          success (bool), message (str).
        """
        if not PYZK_AVAILABLE:
            return {"success": False,
                    "message": "pyzk library not installed."}
        from datetime import datetime as _dt
        target = dt or _dt.now()
        conn = None
        try:
            conn = self.connect(ip, port, password)
            conn.set_time(target)
            self.disconnect()
            return {"success": True,
                    "message": f"Device time set to {target.isoformat()}"}
        except Exception as e:
            if conn:
                try:
                    self.disconnect()
                except Exception:
                    pass
            return {"success": False, "message": str(e)}

    # ── Device Management ─────────────────────────────────────────────────

    def restart_machine(self, ip: str, port: int = 4370, password: str = "") -> dict:
        """Send a restart command to the ZK device.

        Returns dict with keys:
          success (bool), message (str).
        """
        if not PYZK_AVAILABLE:
            return {"success": False,
                    "message": "pyzk library not installed."}
        conn = None
        try:
            conn = self.connect(ip, port, password)
            conn.restart()
            self.disconnect()
            return {"success": True,
                    "message": f"Restart command sent to {ip}:{port}."}
        except Exception as e:
            if conn:
                try:
                    self.disconnect()
                except Exception:
                    pass
            return {"success": False, "message": str(e)}

    # ── User Management ───────────────────────────────────────────────────

    def get_users(self, ip: str, port: int = 4370, password: str = "") -> list:
        """Get list of users registered on the machine."""
        if not PYZK_AVAILABLE:
            return []
        try:
            conn = self.connect(ip, port, password)
            users = conn.get_users()
            self.disconnect()
            return users or []
        except Exception as e:
            logger.debug(f"Error getting users from {ip}: {e}")
            self.disconnect()
            return []

    def _find_free_uid(self, taken_uids, preferred):
        """Return the smallest internal UID >= preferred that is not in *taken_uids*."""
        uid = max(preferred, 1)
        taken = set(taken_uids)
        while uid in taken:
            uid += 1
            if uid > 100_000:   # safety cap; ZK UID is uint32 in practice
                break
        return uid

    def upload_user(self, ip: str, port: int, password: str,
                    uid: int, name: str, privilege: int = 0, user_password: str = "") -> bool:
        """
        Push a single employee to the machine.

        Handles two conflict scenarios:
        1. The employee already exists with a *different* internal UID — reuse
           the existing slot so attendance punches keep linking to the same
           user_id (registration number).
        2. The target UID is occupied by a *different* employee — find the
           next free UID slot so the upload still succeeds.  The ZK protocol
           uses ``user_id`` (the registration-number string) as the business
           key, so changing the internal UID slot is safe: attendance records
           always reference ``user_id``, not ``uid``.
        """
        if not PYZK_AVAILABLE:
            return False
        try:
            conn = self.connect(ip, port, password)

            existing_users = conn.get_users()
            reg_str = str(uid)
            target_uid = uid

            match = next((u for u in existing_users if str(u.user_id) == reg_str), None)
            if match:
                if match.uid != uid:
                    logger.info(f"User {reg_str} exists on {ip} with different UID ({match.uid}). Using existing UID.")
                target_uid = match.uid
            else:
                conflict = next((u for u in existing_users if u.uid == uid), None)
                if conflict:
                    target_uid = self._find_free_uid(
                        [u.uid for u in existing_users], preferred=uid
                    )
                    msg = (f"UID {uid} on {ip} is taken by '{conflict.name}' (UserID: {conflict.user_id}). "
                           f"Uploading {name} to free UID {target_uid} instead.")
                    logger.warning(msg)
                    ErrorReporter.report_warning(msg, context="machine_connector")

            conn.set_user(uid=target_uid, name=name, privilege=privilege,
                          password=user_password, user_id=reg_str)
            self.disconnect()
            return True
        except Exception as e:
            logger.debug(f"Error uploading user {uid} to {ip}: {e}")
            self.disconnect()
            return False

    def delete_user(self, ip: str, port: int, password: str, uid: int) -> bool:
        """Remove a user from the machine (by internal hardware UID)."""
        if not PYZK_AVAILABLE:
            return False
        try:
            conn = self.connect(ip, port, password)
            conn.delete_user(uid=uid)
            self.disconnect()
            return True
        except Exception as e:
            logger.debug(f"Error deleting user {uid} from {ip}: {e}")
            self.disconnect()
            return False

    def delete_user_by_reg(self, ip: str, port: int, password: str, reg_str: str) -> bool:
        """Safely find and remove a user from the machine by their Registration Number / user_id."""
        if not PYZK_AVAILABLE:
            return False
        try:
            conn = self.connect(ip, port, password)
            users = conn.get_users()
            target = next((u for u in users if str(getattr(u, 'user_id', None)) == str(reg_str)), None)
            if not target:
                # Fallback: maybe the internal uid exactly matches the string
                target = next((u for u in users if str(getattr(u, 'uid', None)) == str(reg_str)), None)
                
            if target and hasattr(target, 'uid'):
                conn.delete_user(uid=target.uid)
                self.disconnect()
                return True
            else:
                logger.debug(f"Could not find user with registration/user_id {reg_str} to delete on {ip}.")
                self.disconnect()
                return True
        except Exception as e:
            logger.debug(f"Error deleting user reg {reg_str} from {ip}: {e}")
            self.disconnect()
            return False

    def get_all_templates(self, ip: str, port: int, password: str) -> list:
        """Fetch all biometric templates (fingerprints/faces) from the machine."""
        if not PYZK_AVAILABLE:
            return []
        conn = None
        try:
            conn = self.connect(ip, port, password)
            templates = conn.get_templates()
            
            # If bulk fetch returns nothing, report it - do NOT fall back to
            # the slow per-user scan (294 users x 11 slots = thousands of
            # requests taking 25+ minutes returning nothing on face-only units).
            if not templates:
                logger.info(
                    f"Bulk template fetch returned 0 for {ip}. "
                    f"Device likely stores face data in a secure partition "
                    f"inaccessible via the standard SDK on port {port}."
                )
            
            self.disconnect()
            return templates or []
        except Exception as e:
            logger.debug(f"Error getting templates from {ip}: {e}")
            if conn: self.disconnect()
            return []

    def push_users_bulk(self, ip: str, port: int, password: str, user_list: list,
                        progress_callback=None) -> tuple:
        """
        Push multiple employees to the machine in a single connection session.
        
        user_list: list of dicts with keys 'uid' (int), 'name' (str).
        Returns (success_count, failed_count).
        """
        if not PYZK_AVAILABLE:
            return 0, len(user_list)
        if not user_list:
            return 0, 0

        success = 0
        failed = 0
        conn = None

        try:
            conn = self.connect(ip, port, password)
            existing_users = conn.get_users()
            uid_map = {str(u.user_id): u.uid for u in existing_users}
            taken_uids = {u.uid for u in existing_users}

            for idx, emp in enumerate(user_list):
                if progress_callback:
                    progress_callback(idx + 1, len(user_list))
                try:
                    reg_str = str(emp["uid"])

                    if reg_str in uid_map:
                        # Employee already registered on device - update in place
                        target_uid = uid_map[reg_str]
                    else:
                        # New employee - try to use registration number as internal UID
                        candidate = emp["uid"]
                        if candidate in taken_uids:
                            # Collision: find next free slot above the current max
                            candidate = max(taken_uids) + 1 if taken_uids else 1
                            msg = (f"UID {emp['uid']} for user {reg_str} already taken; "
                                   f"assigned UID {candidate} instead.")
                            ErrorReporter.report_warning(msg, context="machine_connector")
                        taken_uids.add(candidate)   # Reserve for subsequent batch members
                        target_uid = candidate

                    conn.set_user(
                        uid=target_uid,
                        name=emp["name"][:24],
                        privilege=0,
                        password="",
                        user_id=reg_str
                    )
                    success += 1
                except Exception as user_e:
                    logger.debug(f"Failed to push user {emp.get('uid')}: {user_e}")
                    failed += 1

        except Exception as e:
            ErrorReporter.report_warning(f"Bulk push - machine {ip}:{port} not reachable: {e}", context="machine_connector")
            failed = len(user_list)
        finally:
            self.disconnect()

        return success, failed

    def push_biometrics_bulk(self, ip: str, port: int, password: str, templates_data: list, progress_callback=None) -> tuple:
        """
        Accelerated upload of biometric data as integer bitmasks.
        templates_data: list of dicts with 'reg_num', 'type', 'index', 'template_string', 'version'
        """
        if not PYZK_AVAILABLE or not templates_data: return 0, len(templates_data)
        
        success = 0
        failed = 0
        conn = None
        import ast
        from zk.template import Template
        
        try:
            conn = self.connect(ip, port, password)
            existing_users = conn.get_users()
            uid_map = {str(u.user_id): u.uid for u in existing_users}
            
            for idx, item in enumerate(templates_data):
                if progress_callback: progress_callback(idx + 1, len(templates_data))
                
                reg_str = item.get("reg_num")
                target_uid = uid_map.get(reg_str)
                
                if not target_uid:
                    # The user hasn't been pushed to the hardware yet!
                    failed += 1
                    continue
                    
                try:
                    # Convert our stored string back to raw bytes (the integer bitmask form)
                    raw_bytes = ast.literal_eval(item["template_string"])
                    t = Template(
                        uid=target_uid,
                        size=len(raw_bytes),
                        fid=item["index"],
                        valid=1,
                        template=raw_bytes,
                        mark=15 if item["type"] == "face" else 1,
                        version=item["version"]
                    )
                    conn.save_user_template(t)
                    success += 1
                except Exception as e:
                    logger.debug(f"Failed to push bitmask for {reg_str}: {e}")
                    failed += 1
                    
        except Exception as e:
            logger.warning(f"Accelerated bitmask upload failed: {e}")
            failed = len(templates_data)
        finally:
            if conn: self.disconnect()
            
        return success, failed
