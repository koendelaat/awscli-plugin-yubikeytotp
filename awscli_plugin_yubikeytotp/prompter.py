import re

from botocore.exceptions import ProfileNotFound
import subprocess
import sys


def _win_console_print(s):
    for c in s:
        msvcrt.putwch(c)
    msvcrt.putwch("\r")
    msvcrt.putwch("\n")


def _unix_console_print(s):
    with os.fdopen(os.open("/dev/tty", os.O_WRONLY | os.O_NOCTTY), "w", 1,) as tty:
        print(s, file=tty)


try:
    import msvcrt

    console_print = _win_console_print
except ImportError:
    import os

    console_print = _unix_console_print


class YubikeyTotpPrompter(object):
    def __init__(self, original_prompter=None):
        self._original_prompter = original_prompter

    def __call__(self, prompt):
        try:

            prompt_pattern = re.compile('Enter MFA code for (.+): ')
            match = prompt_pattern.match(prompt)

            if match:
                mfa_serial = match.group(1)

                available_keys_result = subprocess.run(
                    ["ykman", "oath", "accounts", "list"], capture_output=True, check=True
                )
                available_keys = available_keys_result.stdout.decode("utf-8").split()
                available_keys.index(mfa_serial)

                console_print(
                    "Generating OATH code on YubiKey. You may have to touch your YubiKey to proceed..."
                )
                ykman_result = subprocess.run(
                    ["ykman", "oath", "accounts", "code", "-s", mfa_serial], capture_output=True
                )
                console_print("Successfully created OATH code.")
                token = ykman_result.stdout.decode("utf-8").strip()
                return token
        except subprocess.CalledProcessError as e:
            print("No YubiKey found.", file=sys.stderr)
        except ValueError as e:
            print(
                "The requested mfa_serial has no OATH credentials stored on your YubiKey.",
                file=sys.stderr,
            )

        if self._original_prompter:
            return self._original_prompter(prompt)

        return None


def inject_yubikey_totp_prompter(session, **kwargs):
    try:
        providers = session.get_component("credential_provider")
    except ProfileNotFound:
        return

    assume_role_provider = providers.get_provider("assume-role")
    original_prompter = assume_role_provider._prompter
    assume_role_provider._prompter = YubikeyTotpPrompter(original_prompter=original_prompter)
