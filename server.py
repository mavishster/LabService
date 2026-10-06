import socket
import threading

from device_handlers import handle_device_data

def start_port_listener(
    port,
    device_info
):
        server = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        try:

            server.bind(
                ("0.0.0.0", port)
            )

            server.listen(5)

            print(
                f"🟢 [*] ЛИС-Сервер запущен. "
                f"Слушаем Порт {port} "
                f"для [{device_info['name']}]"
            )

            while True:

                client_sock, client_addr = (
                    server.accept()
                )

                print(
                    f"🔥 ACCEPT: "
                    f"{client_addr} -> порт {port}"
                )

                threading.Thread(
                    target=handle_device_data,
                    args=(
                        client_sock,
                        device_info
                    ),
                    daemon=True
                ).start()

        except Exception as e:

            print(
                f"💥 Ошибка сокета "
                f"на порту {port}: {e}"
            )

        finally:

            try:
                server.close()

            except Exception:
                pass
