import threading
import time

from config import DEVICES_CONFIG
from server import start_port_listener


def main():
    print(
        "=== ЗАПУСК ЛАБОРАТОРНОГО "
        "ЛИС-СЕРВЕРА КЛИНИКИ ==="
    )

    for port, info in DEVICES_CONFIG.items():

        threading.Thread(
            target=start_port_listener,
            args=(
                port,
                info
            ),
            daemon=True
        ).start()

        time.sleep(0.1)

    try:

        while True:

            time.sleep(1)

    except KeyboardInterrupt:

        print(
            "\n🛑 Работа сервера остановлена."
        )


if __name__ == "__main__":
    main()
