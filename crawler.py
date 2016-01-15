import json
import sys
sys.dont_write_bytecode = True
import requests
import time
import database

MAX_FRIENDS  = 1000
MAX_FOLLOWERS = 1000

from requests_oauthlib import OAuth1

with open("./config.json","r") as content_file:
    config = json.loads(content_file.read())

#authentication pieces
client_key = config["client_key"]
client_secret = config["client_secret"]
token = config["token"]
token_secret = config["token_secret"]

#setup authentication
oauth = OAuth1(client_key,client_secret,token,token_secret)

#Twitter Base Request
def send_request(screen_name,rel_type,next_cursor=None):
    url = "https://api.twitter.com/1.1/%s/ids.json?screen_name=%s&count=5000" % (rel_type,screen_name)

    if next_cursor is not None:
        url += "&cursor=%s" % next_cursor

    response = requests.get(url,auth=oauth)

    #Wait to fix request limit
    time.sleep(4)

    if response.status_code == 200:
        result = json.loads(response.content)
        return result
    else:
        print "[-] Connection Failed Waiting 15 Minutes To Retry"
        time.sleep(900)
        url = "https://api.twitter.com/1.1/%s/ids.json?screen_name=%s&count=5000" % (rel_type,screen_name)

        if next_cursor is not None:
            url += "&cursor=%s" % next_cursor

        response = requests.get(url,auth=oauth)

        if response.status_code == 200:
            result = json.loads(response.content)
            return result
        else:
            print "[-] Connection Failed"
            print "[-] Check Network Connection or Authorization Tokens"
            return None

#users that the user follows
def get_user_friend_list(screen_name):
    print "Screen Name Called: " + screen_name
    friend_list = []
    next_cursor = None

    #init Request
    friends = send_request(screen_name,"friends")

    #if data is returned start collection loop
    if friends is not None:
        friend_list.extend(friends["ids"])
        print "[*] Downloaded %d friends" % len(friend_list)

        #while we have a valid cursor value download friends
        while friends["next_cursor"] != 0 and friends["next_cursor"] != -1:
            friends = send_request(screen_name,"friends",friends["next_cursor"])

            if friends is not None:
                friend_list.extend(friends["ids"])
                print "[*] Downloaded %d friends" % len(friend_list)
            else:
                break

        return friend_list

#users that follow user
def get_user_follower_list(screen_name):
    follower_list = []
    next_cursor = None

    #init Request
    followers = send_request(screen_name,"followers")

    #if data is returned start collection loop
    if followers is not None:
        follower_list.extend(followers["ids"])
        print "[*] Downloaded %d followers" % len(follower_list)

        #while we have a valid cursor value download followers
        while followers["next_cursor"] != 0 and followers["next_cursor"] != -1:
            followers = send_request(screen_name,"followers",followers["next_cursor"])

            if followers is not None:
                follower_list.extend(followers["ids"])
                print "[*] Downloaded %d followers" % len(follower_list)
            else:
                break

        return follower_list

def get_user_info_from_id(user_id):
    print "[+] Getting User Info For ID: %s" % user_id
    url = "https://api.twitter.com/1.1/users/lookup.json?user_id=%s" % user_id
    failed = False
    try:
        response = requests.get(url, auth=oauth)
    except requests.exceptions.ConnectionError:
        print "[-] Connection Limit Reached Waiting 15 Minutes"
        response = type('response', (object,), {})()
        response.status = 403
        time.sleep(900)
        failed = True

    if not failed or response.status_code == 200:
        return json.loads(response.content)
    else:
        print "[-] Connection Failed Waiting 15 Minutes"
        time.sleep(900)
        response = requests.get(url, auth=oauth)
        if response.status_code == 200:
            return json.loads(response.content)
        else:
            print "[-] Check Network Connection or Authorization Tokens"
            return None

def get_user_info_from_screen_name(screen_name):
    url = "https://api.twitter.com/1.1/users/lookup.json?screen_name=%s" % screen_name
    response = requests.get(url, auth=oauth)
    if response.status_code == 200:
        return json.loads(response.content)
    else:
        print "[-] Connection Failed Waiting 15 Minutes"
        time.sleep(900)
        response = requests.get(url, auth=oauth)
        if response.status_code == 200:
            return json.loads(response.content)
        else:
            print "[-] Error Connection"
            return None

def process_ids(ids):
    result = []
    for item in ids:
        temp = get_user_info_from_id(item)
        time.sleep(4)
        try:
            result.extend([temp[0]])
        except:
            print "[-] Error with return value"
            print "[-] JSON OBJECT"
            print json.dumps(temp)
    return result

def procces_data(user_id,user_name,friends,followers):
    #Check if user exists
    if len(database.get_user_from_screen_name(user_name)) == 0:
        database.add_user(user_id,user_name,True)

        database.make_new_friend_table(user_name)

        for f in friends:
            database.add_friend(user_name,f["id"],f["screen_name"])
            database.make_new_follower_table(user_name)

        for f in followers:
            database.add_follower(user_name,f["id"],f["screen_name"])
        print "[+] %s Data Has Been Added" % user_name
    else:
        print "[*] User Already Exists Ignoring"

#Main recursive function
def check(user,degree):
    friend_request = get_user_friend_list(user["screen_name"])
    follower_request = get_user_follower_list(user["screen_name"])

    friends = process_ids(friend_request)
    followers = process_ids(follower_request)

    if degree <= 0:
        procces_data(user["id"],user["screen_name"],friends,followers)
    else:
        for f in friends:
            if int(f["friends_count"]) <= MAX_FRIENDS and int(f["followers_count"]) <= MAX_FOLLOWERS:
                check(f,degree-1)

        for f in followers:
            if int(f["friends_count"]) <= MAX_FRIENDS and int(f["followers_count"]) <= MAX_FOLLOWERS:
                check(f,degree-1)

def is_numeric(value):
    try:
        float(value)
        return True
    except:
        return False

def main():
    print "[+] Starting Twitter Crawler Bot"
    user_input = ""
    while True:
        print "[*] Please Input Degree Limit"
        user_input = raw_input(">> ")
        if is_numeric(user_input):
            break
        else:
            print "[-] Must Be Integer"

    degree = int(user_input)

    user_input = ""
    while user_input == "":
        print "[*] Please Input Starting Node Screen Name"
        user_input = raw_input(">> ")

    if len(database.get_user_from_screen_name(user_input)) != 0:
        print "[-] User already axists"
        print "[+] Please Input Valid Starting Node"
        main()

    else:
        init_friend_request = get_user_friend_list(user_input)
        init_follower_request = get_user_follower_list(user_input)

        starting_node = get_user_info_from_screen_name(user_input)[0]

        init_friends = process_ids(init_friend_request)
        init_followers = process_ids(init_follower_request)

        #Add user data to database
        procces_data(starting_node["id"],starting_node["screen_name"],init_friends,init_followers)

        for f in init_friends:
            if int(f["friends_count"]) <= MAX_FRIENDS and int(f["followers_count"]) <= MAX_FOLLOWERS:
                check(f,degree)

        for f in init_followers:
            if int(f["friends_count"]) <= MAX_FRIENDS and int(f["followers_count"]) <= MAX_FOLLOWERS:
                check(f,degree)

if __name__ == "__main__":
    main()
