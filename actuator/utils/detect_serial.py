# so101_port_detect.py
# pip install pyserial

import time
from serial.tools import list_ports

# --- Known device IDs --------------------------------------------------------
LEADER_SERIAL  = "5A7A057136"  # <-- leader's USB SerialNumber
FOLLOWER_SERIAL = "5A7A057676"  # <-- follower's USB SerialNumber

# Optional filters (narrow to the CH34x/CH9102 ACM device you showed in dmesg)
USB_VID = 0x1A86
USB_PID = 0x55D3


def detect_so101_ports(
    leader_serial: str = LEADER_SERIAL,
    follower_serial: str = FOLLOWER_SERIAL,
    vid: int | None = USB_VID,
    pid: int | None = USB_PID,
    timeout_s: float = 1.0,
    poll_s: float = 0.25,
) -> dict:
    """
    Poll /dev for ttyACM* devices and return {'leader_port': ..., 'follower_port': ...}
    by matching the USB SerialNumber strings for both devices.

    Args:
        leader_serial: USB SerialNumber of the leader device.
        follower_serial: USB SerialNumber of the follower device.
        vid, pid: Optional USB VID/PID filter (set to None to disable).
        timeout_s: How long to poll before failing.
        poll_s: Delay between polls.

    Returns:
        dict with keys 'leader_port', 'follower_port'.

    Raises:
        RuntimeError if either device is not found before timeout.
    """
    t0 = time.time()
    last_seen_acm = []
    last_seen_serials = {}

    def _accept(p):
        if not (p.device and "ttyACM" in p.device):
            return False
        if vid is None or pid is None:
            return True
        return (p.vid == vid) and (p.pid == pid)

    while time.time() - t0 < timeout_s:
        ports = list_ports.comports()
        serial_to_port = {}
        acm_devices = []

        for p in ports:
            if p.device and "ttyACM" in p.device:
                acm_devices.append(p.device)
            if _accept(p) and p.serial_number:
                serial_to_port[p.serial_number] = p.device

        last_seen_acm = acm_devices
        last_seen_serials = serial_to_port

        leader_port = serial_to_port.get(leader_serial)
        follower_port = serial_to_port.get(follower_serial)

        if leader_port and follower_port and leader_port != follower_port:
            return {"leader_port": leader_port, "follower_port": follower_port}

        time.sleep(poll_s)

    return {
        "leader_port": last_seen_serials.get(leader_serial, None),
        "follower_port": last_seen_serials.get(follower_serial, None),
    }


# Example usage
if __name__ == "__main__":
    ports = detect_so101_ports()
    print(ports)