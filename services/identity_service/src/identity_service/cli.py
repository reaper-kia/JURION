import argparse
import asyncio
from getpass import getpass

from identity_service.applications.commands.create_admin import CreateAdmin
from identity_service.dependencies import build_container
from identity_service.infra.config import get_settings


async def create_admin(email: str, nickname: str, password: str) -> None:
    container = build_container(get_settings())
    try:
        user_id = await container.mediator.send(CreateAdmin(email, nickname, password))
        print(f"Created administrator {user_id}")
    finally:
        await container.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a JURION administrator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--nickname", required=True)
    args = parser.parse_args()
    password = getpass("Password: ")
    if password != getpass("Confirm password: "):
        parser.error("Passwords do not match")
    asyncio.run(create_admin(args.email, args.nickname, password))
