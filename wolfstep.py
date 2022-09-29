import asyncio, json, base64, subprocess, time
from urllib.parse import quote
from PIL import Image
from websockets import client, exceptions

"""
you're gonna need to
pip install pix2tex Pillow
everything else should be included in your install
"""





PADDING = 22 # up down padding from eq sign, edit at your will
BOTTOMCROP = 200 # bottom x pixels for looking for eqsign and final result


"""
[{"t":50,"c":[[{"t":0,"v":"Who created you?"}],[{"t":0,"v":"x"}]]}]
int Who created you? dx

test shit, this is in the other format wolfram uses to communicate the math input tab pretty cool huh

"""


async def talk(q, encode=False):
    print("connecting to ws...")
    again = False
    latex = ""
    async with client.connect("wss://www.wolframalpha.com/n/v1/api/fetcher/results", extra_headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36"}) as ws:
        """
        {"type":"init","lang":"en","exp":1664340905848,"displayDebuggingInfo":false,
        "messages":[{"type":"newQuery","locationId":"/input?i=thing","language":"en","displayDebuggingInfo":false,"yellowIsError":false,"requestSidebarAd":false,"input":"thing","i2d":false,"assumption":[],"apiParams":{},"file":null}],"input":"thing","i2d":false,"assumption":[],"apiParams":{},"file":null}
        [{"t":50,"c":[[{"t":0,"v":"Who created you?"}],[{"t":0,"v":"x"}]]}] # int Who created you? dx
        """
        if encode:
            query = base64.b64encode(q.encode()).decode()
        else:
            query = q
        print("sending ws query of", q)
        await ws.send(json.dumps({"type":"init","lang":"en","exp":time.time_ns() // 1000000,"displayDebuggingInfo":False,
            "messages":[{"type":"newQuery","locationId":"/input?i="+quote(q),"language":"en","displayDebuggingInfo":False,
            "yellowIsError":False,"requestSidebarAd":False,"input":q,"i2d":False,"assumption":[],"apiParams":{},
            "file":None}],"input":q,"i2d":False,"assumption":[],"apiParams":{},"file":None})
        )
        c: dict = {"type":""}
        cs = []
        normalcs = []
        try:
            while c["type"] != "queryComplete": # although it may send a step by step after query complete, it is basically guaranteed to be the empty "oops" or one we do not care about
                c = json.loads(await ws.recv())
                if c["type"] == "stepByStep":
                    cs.append(c)
                else:
                    normalcs.append(c)
        except exceptions.ConnectionClosed:
            print("? ws closed")
            return

        inp = -1
        if not cs:
            print("no step by step recieved")
            print("other output pods")
            pods = []
            for p in normalcs:
                if p["type"] == "pods":
                    pods.extend(p["pods"])
            for i in range(len(pods)):
                print(str(i)+":", pods[i]["title"])
            ini = ''
            while inp > len(pods) - 1 or inp < 0:
                    ini = input(":")
                    try:
                        inp = int(ini)
                    except:
                        print("that's not an integer")
                        continue
            print("selected", pods[inp]["title"])
            print("alt:", pods[inp]["subpods"][0]["img"]["alt"])
            with open("out-.png", "wb") as file:
                file.write(base64.b64decode(pods[inp]["subpods"][0]["img"]["data"]))
            print("original recieved data -> out-.png")
            with Image.open("out-.png") as img:
                im = img.convert("RGBA")
                back = Image.new("RGBA", im.size, "WHITE")
                back.paste(im, (0, 0), im)
                origsize = back.size
                back.convert("RGB").save("out.png")
                print("removed alpha channel -> out.png")
            return
        else:
            print("recieved step by step")
            if len(cs) > 1:
                print("recieved more than one")
                print("select one")
                for i in range(len(cs)):
                    print(str(i)+":", cs[i]["pod"]["title"])
                while inp > len(cs) - 1 or inp < 0:
                    ini = input(":")
                    try:
                        inp = int(ini)
                    except:
                        print("that's not an integer")
                        continue
            else:
                inp = 0
                

        
        with open("out-.png", "wb") as file:
            file.write(base64.b64decode(cs[inp]["pod"]["subpods"][0]["img"]["data"]))
        print("original recieved data -> out-.png")


        dims = [0, 0, 0, 0] # left upper right=0 lower
        eqcount = 0
        rows = [] # left top width height


        def hline(im: Image.Image, pxd, position: tuple[int, int]) -> bool:
            x, y = position
            for i in range(min(im.size[0] - x, 8)):
                if pxd[x, y][0] > 120 or pxd[x, y] != pxd[x + 1, y]:
                    return False
            return True

        origsize: Image._Size
        with Image.open("out-.png") as im:
            back = Image.new("RGBA", im.size, "WHITE")
            back.paste(im, (0, 0), im)
            origsize = back.size
            back.convert("RGB").save("out.png")
            print("removed alpha channel -> out.png")
            i = back.crop((0, back.height - BOTTOMCROP, back.width, back.height)).convert("RGB")
            i.save("out-eqsign.png")
            print("searching cropped ver for eqsigns -> out-eqsign.png")
            px = i.load()
            x = y = 0
            for y in range(i.height - 3):
                for x in range(i.width - 1):
                    if hline(i, px, (x, y)) and hline(i, px, (x, y + 3)):
                        eqcount += 1
                        rows.append((x, y, 8, 4))
            print("done, found", eqcount)
            if eqcount == 0:
                return
            
        with Image.open("out.png") as i:
            row = rows[-1]
            print("taking last one", row)
            dims[0] = row[0] + row[2]
            dims[1] = row[1] - PADDING + origsize[1] - BOTTOMCROP
            dims[2] = i.width
            dims[3] = min(row[1] + row[3] + PADDING, i.height) + origsize[1] - BOTTOMCROP
            print("cropping to", dims)
            im = i.crop(dims).convert("RGB")
            newd = []
            thisd = []
            print("darkening...") # for some things visibility, wolfram lightens times for some reason
            for d in im.getdata():
                thisd = list(d)
                if abs(200 - d[0]) < 50:
                    for i in range(3):
                        thisd[i] = int(d[i] ** 0.95)
                newd.append(tuple(thisd))
            im.putdata(newd)
            im.save("out-crop.png")
            print("done -> out-crop.png")
        
        print("done cropping, now pix2tex analyzing out-crop.png")
        latex = subprocess.run(["pix2tex", "-t", "0.1", "out-crop.png"], stdout=subprocess.PIPE).stdout.decode("utf-8").split("out-crop.png: ")[1]
        print("pix2tex done, latex is:")
        print(latex)
        if input("continue? ").lower().startswith("y"):
            again = True

    if again:
        await talk(latex)
            



        

# this is your original query that you actually want to ask it
asyncio.run(talk(input("query? ")))
