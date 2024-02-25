import json
import sys

from lib import bunq
from lib import bunq_api
from lib.config import config


config.parser.add_argument("bunq_user_name",
    help="Bunq user name (retrieve using 'python3 list_user.py')")
config.parser.add_argument("bunq_account_name",
    help="Bunq account name (retrieve using 'python3 list_user.py')")
config.load()

bunq_user_id = bunq_api.get_user_id(config.get("bunq_user_name"))
bunq_account_id = bunq_api.get_account_id(bunq_user_id,
                                               config.get("bunq_account_name"))

method = ("v1/user/{0}/monetary-account/{1}/payment?count=100"
          .format(bunq_user_id, bunq_account_id))
payments = bunq.fetch(method)
for v in [p["Payment"] for p in payments]:
    print("{0:>8} {1:3}  {2}  {3} {4}".format(
        v["amount"]["value"],
        v["amount"]["currency"],
        v["created"][:16],
        v["counterparty_alias"]["iban"],
        v["counterparty_alias"]["display_name"]
    ))
    print("{0:14}Type: {1}/{2}  {3}".format(
        "",
        v["type"],
        v["sub_type"],
        v["description"]
     ))
