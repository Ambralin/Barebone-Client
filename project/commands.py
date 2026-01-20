import requests
import urllib3
import portoken
import base64
from tkinter import Button
from PIL import Image, ImageTk
from io import BytesIO
import threading
import websocket
import json
import ssl
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


BASE_PATH = Path(__file__).resolve().parent
ASSETS_PATH = BASE_PATH / "assets"

def relative_to_assets(path: str) -> Path:
    return ASSETS_PATH / Path(path)

class Theme:
    def __init__(self, accent="#1BB9FD", accent_dark="#0084BD", warning="#EF4E4E", warning_dark="#C51616", bg_dark="#101010", bg_dim="#191919", bg_medium="#222222", bg_light="#2A2A2A", fg="#DADADA"):
        self._values = {
            "accent": accent,
            "accent_dark": accent_dark,
            "warning": warning,
            "warning_dark": warning_dark,
            "bg_dark": bg_dark,
            "bg_dim": bg_dim,
            "bg_medium": bg_medium,
            "bg_light": bg_light,
            "fg": fg
        }

    def set(self, key: str, value: str):
        if not isinstance(value, str):
            raise TypeError("Theme values must be strings")
        self._values[key] = value

    def get(self, key: str, default: str = "") -> str:
        return self._values.get(key, default)

    def __getattr__(self, name):
        if name in self._values:
            return self._values[name]
        raise AttributeError(f"'Theme' object has no attribute '{name}'")
    
deftheme = Theme()


token, port = portoken.get_lcu_token_and_port()
url = f"https://127.0.0.1:{port}"
auth = f"riot:{token}"
b = bytearray()
b.extend(map(ord, auth))
auth = base64.b64encode(b)
headers = {"Authorization": f"Basic {str(auth)[2:-1]}"}

def on_message(ws, message):
    if not message: return
    try:
        payload = json.loads(message)
    except json.JSONDecodeError:
        return

    if not isinstance(payload, list) or len(payload) < 3:
        return

    opcode, event_name, event = payload

    #print(event.get("uri"))

    if opcode != 8:
        return

    if event.get("uri") == "/lol-lobby/v2/lobby":
        lobby = event.get("data")
        updateLobby(lobby)

    if event.get("uri") == "/lol-lobby/v2/lobby/matchmaking/search-state":
        queueData = event.get("data")
        showQueue(queueData)

def on_open(ws):
    ws.send(json.dumps([
        5,
        "OnJsonApiEvent_lol-lobby_v2_lobby"
    ]))

def on_error(ws, error):
    print("WS ERROR:", error)

def on_close(ws, close_status, close_msg):
    print("WS CLOSED:", close_status, close_msg)

def start_ws(port, token):
    auth = base64.b64encode(f"riot:{token}".encode()).decode()

    ws = websocket.WebSocketApp(
        f"wss://127.0.0.1:{port}/",
        header=[f"Authorization: Basic {auth}"],
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    ws.run_forever(
        sslopt={"cert_reqs": ssl.CERT_NONE}
    )

threading.Thread(
    target=start_ws,
    args=(port, token),
    daemon=True
).start()

tkqueuebtn = None
tkframes = []
tkrole_Images = []
role_positions = {}
tkselectors = None
currentRoleSelecting = ""

lobbyTypes = {

"swiftplay" : {
    "queueId": 480,
    "isRanked": False,
    "isCustom": False
},
"draft" : {
    "queueId": 400,
    "isRanked": False,
    "isCustom": False
},
"soloq" : {
    "queueId": 420,
    "isRanked": True,
    "isCustom": False
},
"flex" : {
  "queueId": 440,
  "isRanked": True,
  "isCustom": False
},
"aram" : {
    "queueId": 450,
    "teamSize": 5,
    "customGameName": "Custom ARAM Lobby",
    "mapId": 12,
    "pickType": "ALL_RANDOM",
    "spectatorPolicy": "AllAllowed"
},
"mayhem" : {
    "queueId": 2400,
    "teamSize": 5,
    "customGameName": "Custom ARAM Lobby",
    "mapId": 12,
    "pickType": "ALL_RANDOM",
    "spectatorPolicy": "AllAllowed"
},
"arena": {
    "queueId": 1700,       
    "teamSize": 2,
    "customGameName": "Arena Standard Lobby",
    "mapId": 30,
    "pickType": "DRAFT",
    "spectatorPolicy": "AllAllowed"
},

}

def makeRequest(reqType, cusUrl, cusJson=None, extraUrl=""):
    if reqType == "GET":
        result = requests.get(url+cusUrl+extraUrl, json=cusJson, headers=headers, verify=False)
    elif reqType == "POST":
        result = requests.post(url+cusUrl+extraUrl, json=cusJson, headers=headers, verify=False)
    elif reqType == "DELETE":
        result = requests.delete(url+cusUrl+extraUrl, json=cusJson, headers=headers, verify=False)
    elif reqType == "PUT":
        result = requests.put(url+cusUrl+extraUrl, json=cusJson, headers=headers, verify=False)
    else:
        print("set correct request type")
        return False
    
    if result.content:
        return result.json()
    else:
        return False


lobby = f"/lol-lobby/v2/lobby"
matchmaking = "/lol-lobby/v2/lobby/matchmaking/search"
summoner = "/lol-summoner/v1/current-summoner"

playerId = 0

def getSummoner(canvas, text_id, icon):
    global playerId
    result = makeRequest("GET", summoner)
    playerId = result["summonerId"]
    canvas.itemconfig(text_id, text=result["gameName"])
    tk_img = getIconFromId(result['profileIconId'], 120)
    canvas.itemconfig(icon, image=tk_img)
    if not hasattr(canvas, "_images"):
        canvas._images = {}
    canvas._images[icon] = tk_img

def getLobby():
    result = makeRequest("GET", lobby)
    return result

def setLobby(lobbyId:str, allButtons):
    global tkselectors
    for button in allButtons.values():
        button.config(bg=deftheme.bg_dark)
    
    allButtons[lobbyId].config(bg=deftheme.bg_light)
    makeRequest("POST", lobby, lobbyTypes[lobbyId])
    if tkselectors != None:
        tkselectors.place_forget()
    showRoles()

def saveRoles(role_Images):
    global tkrole_Images
    tkrole_Images = role_Images
    for role in tkrole_Images:
        role_positions[role] = role.place_info()

def showRoles():
    global tkrole_Images
    result = getLobby()
    dontdrawnext = False
    try:
        showing_roles = result["gameConfig"]["showPositionSelector"]
        for role in tkrole_Images:
            if showing_roles and dontdrawnext == False:
                if role in role_positions:
                    role.place(**role_positions[role])

                    roleimg = getRoleFromName(result["localMember"][f"{'first' if str(role) == '.prim' else 'second'}PositionPreference"], 50)
                    role.config(image=roleimg)
                    role.image = roleimg
                    if result["localMember"]["firstPositionPreference"] == "FILL":
                        newpos = role_positions[role].copy()
                        newpos["x"] = 185
                        role.place(**newpos)
                        dontdrawnext = True
                    else:
                        role.place(**role_positions[role])
            else:
                role.place_forget()
    except:
        return
    
def postRole(selector_Images, role_Name):
    currlobby = getLobby()
    firstpos = role_Name if currentRoleSelecting == "first" else currlobby["localMember"]["firstPositionPreference"]
    secondpos = role_Name if currentRoleSelecting == "second" else currlobby["localMember"]["secondPositionPreference"]
    body = { f"firstPreference": firstpos, "secondPreference": secondpos}
    makeRequest("PUT", "/lol-lobby/v1/lobby/members/localMember/position-preferences", body)
    showRoles()
    selector_Images.place_forget()


def startQueue():
    if makeRequest("GET", lobby):
        makeRequest("POST", matchmaking)

def stopQueue():
    makeRequest("DELETE", matchmaking)

def queueState():
    result = makeRequest("GET", matchmaking, None, "-state")
    return result

def manageQueue(queueButton, start=False, reset=False):
    global tkqueuebtn
    tkqueuebtn = queueButton
    result = queueState()
    currQueueState = result["searchState"]
    if currQueueState == "Invalid" and start:
        startQueue()
        queueButton.config(bg=deftheme.warning, activebackground=deftheme.warning_dark, text="STOP QUEUE")
    elif currQueueState == "Searching" and reset or currQueueState == "Found":
        stopQueue()
        queueButton.config(bg=deftheme.accent, activebackground=deftheme.accent_dark, text="FIND MATCH")

def showQueue(queueJson):
    result = queueJson
    currQueueState = result["searchState"]
    if currQueueState == "Found":
        accept_button = Button(
            text="ACCEPT",
            fg="white",
            font=("Inter SemiBold", 25 * -1),
            borderwidth=0,
            highlightthickness=0,
            command=lambda: acceptQueue(accept_button),
            bg=deftheme.accent
        )
        accept_button.place(
            x=225.0,
            y=145.0,
            width=250.0,
            height=100.0
        )
        
def acceptQueue(acceptButton):
    makeRequest("POST", "/lol-matchmaking/v1/ready-check/accept")
    acceptButton.place_forget()
    manageQueue(tkqueuebtn)

def manageRoles(pickButton, roleButtonFrame, roleButtons):
    global currentRoleSelecting, tkselectors
    tkselectors = roleButtonFrame
    info = pickButton.place_info()
    roleButtonFrame.place(x=int(info['x'])-25, y=int(info['y'])-60, width=335, height=60)

    if "prim" in str(pickButton):
        currentRoleSelecting = "first"
    else:
        currentRoleSelecting = "second"

def setupFrames(frames):
    global tkframes
    tkframes = frames
    updateLobby(getLobby())

def updateLobby(lobbyJson):
    global playerId
    manageQueue(tkqueuebtn)

    try:
        if lobbyJson["httpStatus"] != 200: return
    except:
        members = lobbyJson["members"]

    for i, member in enumerate(members): #ignoring myself
        if member["summonerId"] == playerId:
            myself = members.pop(i)
    for i, member_data in enumerate(members):
        if i < len(tkframes):
            frame = tkframes[i]
            frame.place(x=310, y=[10, 105, 200, 295][i])
            for widget in frame.winfo_children():
                cls = widget.__class__.__name__

                if cls == "Label":
                    if str(widget) == f"{frame._w}.name":
                        nameJson = makeRequest("GET", "/lol-summoner/v1/summoners", None, "/"+str(member_data["summonerId"]))
                        widget.config(text=nameJson["gameName"])
                    elif str(widget) == f"{frame._w}.icon_label":
                        icon_img = getIconFromId(member_data["summonerIconId"], 65)
                        widget.config(image=icon_img)
                        frame.images["icon"] = icon_img

                    elif str(widget) == f"{frame._w}.prim_icon" and member_data["firstPositionPreference"]:
                        primrole_img = getRoleFromName(member_data["firstPositionPreference"], 30)
                        widget.config(image=primrole_img)
                        frame.images["primrole"] = primrole_img 
                    elif str(widget) == f"{frame._w}.sec_icon" and member_data["secondPositionPreference"]:
                        secrole_img = getRoleFromName(member_data["secondPositionPreference"], 30)
                        widget.config(image=secrole_img)
                        frame.images["secrole"] = secrole_img

                elif cls == "Button":
                    if str(widget) == f"{frame._w}.promote":
                        widget.config(command=lambda m=member_data: makeRequest("POST", lobby, None, f"/members/{m['summonerId']}/promote"))
                        if myself["isLeader"] == False:
                            widget.place_forget()
                    elif str(widget) == f"{frame._w}.kick":
                        widget.config(command=lambda m=member_data: makeRequest("POST", lobby, None, f"/members/{m['summonerId']}/kick"))
                        if myself["allowedKickOthers"] == False:
                            widget.place_forget()


    for j in range(len(members), len(tkframes)):
        tkframes[j].place_forget()

def getIconFromId(id, size):
    return ImageTk.PhotoImage(Image.open(BytesIO(requests.get( f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/profile-icons/{id}.jpg" ).content)).resize((size,size)))

def getRoleFromName(name, size):
    path = relative_to_assets(f"roles\\{name}.png")
    return ImageTk.PhotoImage(Image.open(path).resize((size,size)))