"""Admin commands, run on the server inside the venv:

    python manage.py add-device NIVA-A1F3        # prints the device key once (goes in firmware secrets.h)
    python manage.py pair NIVA-A1F3 1            # link a device to a field without the app
    python manage.py fields                      # list fields with their owner tokens
    python manage.py devices                     # list devices
"""
import secrets
import string
import sys

from sqlmodel import Session, select

from models import Device, FieldRow, engine, hash_key, init_db

APP_URL = "https://david-zaev.github.io/niva"


def pair_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def main(argv: list[str]) -> None:
    init_db()
    cmd = argv[0] if argv else "help"
    with Session(engine) as s:
        if cmd == "add-device" and len(argv) == 2:
            dev_id = argv[1].strip().upper()
            if s.get(Device, dev_id):
                sys.exit(f"{dev_id} already exists")
            key = secrets.token_urlsafe(24)
            dev = Device(id=dev_id, key_hash=hash_key(key), pair_code=pair_code())
            s.add(dev)
            s.commit()
            print(f"device_id  {dev_id}\ndevice_key {key}\npair_code  {dev.pair_code}")
            print(f"pair_link  {APP_URL}/pair?d={dev_id}&c={dev.pair_code}   (make this the QR sticker)")
            print("Save the key now: the server keeps only its hash.")
        elif cmd == "pair" and len(argv) == 3:
            dev = s.get(Device, argv[1].strip().upper())
            field = s.get(FieldRow, int(argv[2]))
            if not dev or not field:
                sys.exit("unknown device or field")
            dev.field_id = field.id
            s.add(dev)
            s.commit()
            print(f"{dev.id} -> field {field.id} ({field.name})")
        elif cmd == "fields":
            for f in s.exec(select(FieldRow)).all():
                print(f.id, f.name, f.lat, f.lon, f.region, f.owner_token, sep="\t")
        elif cmd == "devices":
            for d in s.exec(select(Device)).all():
                print(d.id, d.pair_code, d.field_id, d.last_seen, sep="\t")
        else:
            print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
