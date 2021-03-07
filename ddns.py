import requests, json, time, yaml, datetime, random


class Ddns():
    def __init__(self, config_path):
        if not self.load_config(config_path):
            print("[ERROR] Could not load config file. Exiting.")
            return

        self.run()

    def load_config(self, path):
        with open(path, 'r') as stream:
            try:
                self.config = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
                return False
        return True

    def run(self):
        for job in self.config['jobs']:

            if job['provider'] == "hetzner":
                provider = Hetzner()

            required = provider.required_config()

            config = {}

            for r in required:
                if r in job:
                    config[r] = job[r]
                else:
                    print(f"Missing setting in job: {r}")
                    return False

            provider.set_config(config)

            ip = self.get_ip()

            if not ip:
                print("[ERROR] Not able to fetch your IP. Exiting.")
                return False

            if provider.update_dns(ip):
                return True
            else:
                print("[ERROR] DNS Update failed.")
                return False

    def get_ip(self):
        try:
            resp = requests.get(url="http://ip.stored.cc")
            return resp.content.decode('utf-8').replace(" ", "").replace("\n", "")
        except:
            return False


class Hetzner():

    def __init__(self):
        self.config_set = False

    def required_config(self):
        return ['api_key', 'names', 'save_path', 'zone']

    def set_config(self, config):
        self.api_key = config['api_key']
        self.names = config['names']
        self.path = config['save_path']
        self.zone = config['zone']
        self.records = []
        self.config_set = True

    def send_request(self, method, endpoint, data):
        print(f"[DEBUG] Sending request to API with {data} to {endpoint}")
        headers = {
            "Content-Type": "application/json",
            "Auth-API-Token": self.api_key,
        }

        try:
            if method == "GET":
                resp = requests.get(url="https://dns.hetzner.com/api/v1/" + str(endpoint), headers=headers, data=json.dumps(data))
            elif method == "PUT":
                resp = requests.put(url="https://dns.hetzner.com/api/v1/" + str(endpoint), headers=headers, data=json.dumps(data))
            else:
                resp = requests.request(method, "https://dns.hetzner.com/api/v1/" + str(endpoint), headers=headers, data=json.dumps(data))
        except Exception as e:
            print(e)
            return False

        #print(resp.status_code)
        #print(resp.content)

        if resp.status_code != 200:
            return False
        return json.loads(resp.content.decode('utf-8'))

    def update_dns(self, ip):
        if not self.config_set:
            print("[ERROR] No config set.")
            return False

        if not self.load_data():
            print("[WARNING] Could not load data file. Creating new one.")

            zone_id = self.get_zone_id(self.zone)
            if not zone_id:
                print("[ERROR] Can not get Zone Id")
                return False
            self.data = {"records": {}, "zone": {'name': self.zone, 'id': zone_id, 'created': int(time.time())}}

            if not self.save_data():
                print(f"[ERROR] Could not save data file to {self.path}. Exiting.")
                return False

        for name in self.names:
            if name in self.data['records'] and int(time.time()) - self.data['records'][name]['created'] < (21600 + random.randint(-300, 300)):
                record = self.data['records'][name]
            else:
                id = self.get_record_id(name, ip)
                if not id:
                    print(f"[WARNING] Getting id of {name} failed")
                    continue
                record = {'id': id, 'created': int(time.time()), 'ip': ""}
                self.data['records'][name] = record

            if record['ip'] != ip:
                if self.update_ip(name, record, ip):
                    self.data['records'][name]['ip'] = ip
                else:
                    print(f"[WARNING] IP update for {name} failed")

        if not self.save_data():
            print(f"[ERROR] Could not save data file to {self.path}. Exiting.")
            return False

        return True

    def load_data(self):
        try:
            self.data = json.load(open(self.path))
        except Exception as e:
            print(e)
            return False
        return True

    def save_data(self):
        with open(self.path, 'w') as stream:
            try:
                json.dump(self.data, stream)
            except Exception as e:
                print(e)
                return False
        return True

    def get_zone_id(self, zone):
        zones = self.send_request("GET", "zones", {})

        if not zones:
            return False

        for z in zones['zones']:
            if z['name'] == zone:
                return z['id']

        return False

    def get_record_id(self, name, ip):
        if len(self.records) < 1:
            data = {
                "zone_id": self.data['zone']['id']
            }
            self.records = self.send_request("GET", "records", data)['records']
            if not self.records:
                self.records = []
                return False

        for r in self.records:
            if r['type'] == 'A' and r['name'] == name:
                return r['id']

        id = self.create_record(name, ip)

        if not id:
            return False

        return id

    def update_ip(self, name, record, ip):
        data = {
            "value": ip,
            "ttl": 300,
            "type": "A",
            "name": name,
            "zone_id": self.data['zone']['id']
        }
        
        if not self.send_request("PUT", "records/" + str(record['id']), data):
            return False
        return True

    def create_record(self, name, ip):
        data = {
            "value": ip,
            "ttl": 300,
            "type": "A",
            "name": name,
            "zone_id": self.data['zone']['id']
        }

        resp = self.send_request("POST", "records", data)

        if not resp:
            return False

        return resp['record']['id']

while True:
    d = Ddns("config.yml")
    time.sleep(60*10)

