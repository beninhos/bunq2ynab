from decimal import Decimal
import json
import os
import requests
import uuid
import sys


url = 'https://api.youneedabudget.com/'
personal_access_token_file = "personal_access_token.txt"

# 1 to log http calls, 2 to include headers
log_level = 0


# -----------------------------------------------------------------------------

def read_file(fname):
    dname = os.path.dirname(sys.argv[0])
    fn = os.path.join(dname, fname)
    if os.path.isfile(fn):
        with open(fn, 'r') as f:
            return f.read()


def get_personal_access_token():
    token = read_file(personal_access_token_file)
    if token:
        return token.rstrip("\r\n")
    raise Exception(
        "Couldn't read YNAB personal access token.  Get one " +
        "from YNAB's developer settings and store it in " +
        personal_access_token_file)


# -----------------------------------------------------------------------------

def log_request(action, method, headers, data):
    if log_level < 1:
        return
    print("******************************")
    print("{0} {1}".format(action, method))
    if log_level > 1:
        for k, v in headers.items():
            print("  {0}: {1}".format(k, v))
    if data:
        print("-----")
        print(json.dumps(data, indent=2))
        print("-----")


def log_reply(reply):
    if log_level < 1:
        return
    print("Status: {0}".format(reply.status_code))
    if log_level > 1:
        for k, v in reply.headers.items():
            print("  {0}: {1}".format(k, v))
    print("----------")
    if reply.headers["Content-Type"].startswith("application/json"):
        print(json.dumps(reply.json(), indent=2))
    else:
        print(reply.text)
    print("******************************")


def call(action, method, data_obj=None):
    data = json.dumps(data_obj) if data_obj else ''
    headers = {
        'Authorization': 'Bearer ' + get_personal_access_token(),
        'Content-type': 'application/json'
    }
    log_request(action, method, headers, data_obj)
    if action == 'GET':
        reply = requests.get(url + method, headers=headers)
    elif action == 'POST':
        reply = requests.post(url + method, headers=headers, data=data)
    log_reply(reply)
    result = reply.json()
    if "error" in result:
        raise Exception("{0} (details: {1})".format(
                           result["error"]["name"], result["error"]["detail"]))
    return result["data"]


# -----------------------------------------------------------------------------

def is_uuid(id):
    try:
        uuid.UUID("{" + id + "}")
        return True
    except ValueError as e:
        return False


def get_budget_id(budget_name):
    if is_uuid(budget_name):
        return budget_name

    reply = get('v1/budgets')
    for b in reply["budgets"]:
        if b["name"].casefold() == budget_name.casefold():
            return b["id"]
    raise Exception("YNAB budget '{0}' not found".format(budget_name))


def get_account_id(budget_id, account_name):
    if is_uuid(account_name):
        return account_name

    reply = get('v1/budgets/' + budget_id + "/accounts")
    for a in reply["accounts"]:
        if a["name"].casefold() == account_name.casefold():
            return a["id"]
    raise Exception("YNAB account '{0}' not found".format(account_name))


def upload_transactions(budget_id, account_id, transactions):
    ynab_transactions = []
    for t in transactions:
        milliunits = str((1000 * Decimal(t["amount"])).quantize(1))
        # Calculate import_id for YNAB duplicate detection
        occurrence = 1 + len([y for y in ynab_transactions
                      if y["amount"] == milliunits and y["date"] == t["date"]])
        ynab_transactions.append({
            "account_id": account_id,
            "date": t["date"],
            "amount": milliunits,
            "payee_name": t["payee"][:50],  # YNAB payee is max 50 chars
            "memo": t["description"][:100],  # YNAB memo is max 100 chars
            "cleared": "cleared",
            "import_id": "YNAB:{}:{}:{}".format(
                                             milliunits, t["date"], occurrence)
        })

    method = "v1/budgets/" + budget_id + "/transactions/bulk"
    result = post(method, {"transactions": ynab_transactions})
    return result["bulk"]


# -----------------------------------------------------------------------------

def set_log_level(level):
    global log_level
    log_level = level


def get(method):
    return call('GET', method)


def post(method, data):
    return call('POST', method, data)
