import argparse
import atexit
import errno
import socket
import time

import bunq
import bunq_api
import ynab
import network


# ----- Parameters

firstport = 44716
lastport = 44971
bunq_network = "185.40.108.0/22"


# ----- Parse command line arguments

parser = argparse.ArgumentParser()
parser.add_argument("-v", action="store_true",
    help="Show content of JSON messages")
parser.add_argument("-vv", action="store_true",
    help="Show JSON messages and HTTP headers")
parser.add_argument("--port", type=int,
    help="TCP port number to listen to.  Default is to use the first free " +
         "port in the {0}-{1} range.".format(firstport, lastport))
parser.add_argument("bunq_user_name",
    help="Bunq user name (retrieve using 'python3 list_user.py')")
parser.add_argument("bunq_account_name",
    help="Bunq account name (retrieve using 'python3 list_user.py')")
parser.add_argument("ynab_budget_name",
    help="YNAB user name (retrieve using 'python3 list_budget.py')")
parser.add_argument("ynab_account_name",
    help="YNAB account name (retrieve using 'python3 list_budget.py')")
args = parser.parse_args()
log_level = 2 if args.vv else 1 if args.v else 0
bunq.set_log_level(log_level)


print("Getting BUNQ identifiers...")
bunq_user_id = bunq_api.get_user_id(args.bunq_user_name)
bunq_account_id = bunq_api.get_account_id(bunq_user_id, args.bunq_account_name)

print("Getting YNAB identifiers...")
ynab_budget_id = ynab.get_budget_id(args.ynab_budget_name)
ynab_account_id = ynab.get_account_id(ynab_budget_id, args.ynab_account_name)


# ----- Adding a callback to the bunq account

def add_callback(port):
    public_ip = network.get_public_ip()
    if public_ip != network.get_local_ip():
        network.upnp_portforward(port)
    url = "https://{}:{}/bunq2ynab-autosync".format(public_ip, port)
    print("Adding BUNQ callback to: {}".format(url))
    set_autosync_callbacks([{
        "category": "MUTATION",
        "notification_target": url
    }])


def remove_callback():
    network.upnp_cleanup()
    set_autosync_callbacks([])


def set_autosync_callbacks(new_nfs):
    old_nfs = bunq_api.get_callbacks(bunq_user_id, bunq_account_id)
    for nfi in old_nfs:
        for nf in nfi.values():
            if (nf["category"] == "MUTATION" and
                    nf["notification_target"].endswith("/bunq2ynab-autosync")):
                print("Removing old callback...")
            else:
                new_nfs.append({
                    "category": nf["category"],
                    "notification_target": nf["notification_target"]
                })
    bunq_api.put_callbacks(bunq_user_id, bunq_account_id, new_nfs)


# ----- Synchronize with YNAB

def sync():
    print(time.strftime('%Y-%m-%d %H:%M:%S') + " Reading list of payments...")
    transactions = bunq_api.get_transactions(bunq_user_id, bunq_account_id)
    print("Uploading transactions to YNAB...")
    stats = ynab.upload_transactions(ynab_budget_id, ynab_account_id,
                                     transactions)
    print("Uploaded {0} new and {1} duplicate transactions.".format(
          len(stats["transaction_ids"]), len(stats["duplicate_import_ids"])))
    print(time.strftime('%Y-%m-%d %H:%M:%S') + " Finished sync")
    print("")


# ----- Listen for bunq calls and run scheduled jobs

def bind_port():
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if args.port:
        serversocket.bind(('0.0.0.0', args.port))
        return serversocket, args.port
    for port in range(firstport, lastport+1):
        try:
            serversocket.bind(('0.0.0.0', port))
            return serversocket, port
        except OSError as e:
            if e.errno == errno.EADDRINUSE:
                print("Port {0} is in use, trying next port...".format(port))
                continue
            raise
    raise Exception("No free port found")


serversocket, port = bind_port()
print("Registering callback for port {0}...".format(port))
add_callback(port)
atexit.register(remove_callback)
print("Listening on port {0}...".format(port))
serversocket.listen(5)
while True:
    (clientsocket, address) = serversocket.accept()
    clientsocket.close()
    print("Incoming call from {0}...".format(address[0]))
    if network.addressInNetwork(address[0], bunq_network):
        try:
            sync()
        except Exception as e:
            print("An error occured: {0}".format(e))
    else:
        print("Not from BUNQ {} range, ignoring...".format(bunq_network))
