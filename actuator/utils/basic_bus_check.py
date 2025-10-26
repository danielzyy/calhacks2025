import sys, time, serial
from serial.rs485 import RS485Settings

PORT = "/dev/ttyACM1"   # you said this is correct
BAUDS = [1_000_000, 115_200, 500_000]  # try all
TIMEOUT = 0.15          # seconds
TRY_UNICAST_IDS = [1,2,3,4,5,6]        # your expected IDs

# ---- Protocol helpers (Dynamixel v1 / Feetech-like) ----
def dxl_v1_checksum(byte_list):
    # checksum = ~sum(ID..last) & 0xFF (sum excludes the two 0xFF headers)
    return (~(sum(byte_list) & 0xFF)) & 0xFF

def make_broadcast_ping():
    # 0xFF 0xFF 0xFE 0x02 0x01 CHK
    body = [0xFE, 0x02, 0x01]
    return bytes([0xFF,0xFF] + body + [dxl_v1_checksum(body)])

def make_unicast_ping(id_):
    # 0xFF 0xFF ID 0x02 0x01 CHK
    body = [id_, 0x02, 0x01]
    return bytes([0xFF,0xFF] + body + [dxl_v1_checksum(body)])

def parse_status_packets(buf):
    """
    Naive parser: looks for 0xFF 0xFF, then ID, LEN, ERR, PARAMS, CHK.
    Returns list of (id,len,err,params,raw).
    """
    packets = []
    i = 0
    while i + 4 < len(buf):
        if buf[i] == 0xFF and buf[i+1] == 0xFF:
            if i + 4 >= len(buf):
                break
            sid = buf[i+2]
            ln  = buf[i+3]
            end = i + 4 + ln  # ln includes (error + params + checksum)
            if end < len(buf):
                err = buf[i+4]
                params = buf[i+5:end-1]
                chk = buf[end-1]
                # verify checksum on [ID, LEN, ERR, PARAMS...]
                calc = dxl_v1_checksum([sid, ln, err] + list(params))
                if chk == calc:
                    packets.append((sid, ln, err, bytes(params), bytes(buf[i:end+0])))
                    i = end
                    continue
        i += 1
    return packets

def try_one_baud(baud, use_rs485=False):
    print(f"\n=== BAUD {baud} ===")
    # If your adapter needs RTS to control DE (RS-485), enable rs485_mode with RTS high on send:
    ser = serial.Serial(
        PORT, baudrate=baud, timeout=TIMEOUT,
        # bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE
    )
    if use_rs485:
        ser.rs485_mode = RS485Settings(rts_level_for_tx=True, rts_level_for_rx=False, delay_before_tx=0, delay_before_rx=0)
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        # 1) Broadcast ping
        pkt = make_broadcast_ping()
        ser.write(pkt)
        ser.flush()
        time.sleep(0.03)
        rx = ser.read(512)
        print(f"Broadcast TX: {pkt.hex()}   RX({len(rx)}): {rx.hex()}")
        found = parse_status_packets(rx)
        if found:
            print("  -> Parsed replies:")
            for sid, ln, err, params, raw in found:
                print(f"     ID={sid:3d}  len={ln:02X}  err=0x{err:02X}  params={params.hex()}  raw={raw.hex()}")

        # 2) Unicast pings to your expected IDs
        for sid in TRY_UNICAST_IDS:
            ser.reset_input_buffer()
            upkt = make_unicast_ping(sid)
            ser.write(upkt)
            ser.flush()
            time.sleep(0.02)
            urx = ser.read(128)
            parsed = parse_status_packets(urx)
            status = "none"
            if parsed:
                status = f"OK from ID {parsed[0][0]}"
            print(f"Unicast ID {sid:3d}: TX {upkt.hex()}   RX({len(urx)}): {urx.hex()}   -> {status}")

        return True
    finally:
        ser.close()

if __name__ == "__main__":
    # If you KNOW you're on RS-485 with a dongle that requires RTS for direction, set to True:
    USE_RS485_DIRECTION = False
    for b in BAUDS:
        try_one_baud(b, use_rs485=USE_RS485_DIRECTION)
