try: from utils import smartsplit
except: from .utils import smartsplit
import ssl
import gzip
import json
import os
import os.path
import re
import sys
import time
try:
	import urllib.parse as urllibparse
	import urllib.request as urllibrequest
	import urllib.error as urlliberror
except ImportError:
	import urllib as urllibrequest
	import urllib as urllibparse
	import urllib as urlliberror
sys.path.insert(0, os.path.dirname(__file__))
import socks
try: from sockshandler import SocksiPyHandler
except ImportError: from .sockshandler import SocksiPyHandler
del sys.path[0]

class YandexFreeTranslateError(Exception): pass

class YandexFreeTranslate():
	error_count = 0
	broker1 = 'http://alekssamosbt.ru/yt.php'
	siteurl = "https://translate.yandex.ru/"
	apibaseurl = "https://translate.yandex.net/api/v1/tr.json/"
	api=""
	ua = r"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:79.0) Gecko/20100101 Firefox/79.0"
	key = ""
	keysuffix = "-0-0"
	keyfilename = os.path.join(os.path.expanduser("~"), ".YandexFreeTranslate.key")
	expiretime = 60*60*24*4
	backfilename = keyfilename+".back"
	useProxy = False
	proxy_protocol = ""
	proxy_host = ""
	proxy_port = 0
	proxy_username = ""
	proxy_password = ""
	def _getparams(self, **p):
		params = {}
		params["ios"] = {
			"srv":"ios", "ucid":"9676696D-0B56-4F13-B4D5-4A3DA2A3344D",
			"sid":"1A5A10A952AB4A3B82533F44B87EE696", "id":"1A5A10A952AB4A3B82533F44B87EE696-0-0"
		}
		params["web"] = {
			"id":self.key, "srv":"tr-text", "reason":"paste", "options": 4
		}
		params["broker1"] = {}
		params[self.api].update(p)
		return params[self.api]
	def decode_response(self, response):
		try:
			res = response.decode("UTF8")
		except UnicodeDecodeError:
			res = gzip.decompress(response).decode("UTF8")
		return res

	def setProxy(self, protocol, host, port, username="", password=""):
		self.useProxy = True
		self.proxy_protocol = protocol
		self.proxy_host = host
		self.proxy_port = int(port)
		self.proxy_username = username
		self.proxy_password = password

	def _create_opener(self):
		opener = urllibrequest.build_opener()
		if self.useProxy:
			if self.proxy_protocol == "socks4":
				opener = urllibrequest.build_opener(SocksiPyHandler(socks.SOCKS4,
					self.proxy_host, self.proxy_port, username=self.proxy_username, password=self.proxy_password))
			if self.proxy_protocol == "socks5":
				opener = urllibrequest.build_opener(SocksiPyHandler(socks.SOCKS5,
					self.proxy_host, self.proxy_port, username=self.proxy_username, password=self.proxy_password))
		return opener

	def _create_request(self, *ar, **kw):
		if len(ar) > 0 and "http" in ar[0]: url = ar[0]
		if "url" in kw: url = kw["url"]
		rq = urllibrequest.Request(*ar, **kw)
		if self.useProxy:
			if self.proxy_protocol == "http" or self.proxy_protocol == "https":
				fullHost = ":".join([self.proxy_host, str(self.proxy_port)])
				if len(self.proxy_username) + len(self.proxy_password) > 0:
					fullHost = ":".join([self.proxy_username, self.proxy_password]) + "@" + fullHost
				rq.set_proxy(fullHost, self.proxy_protocol)
			rq.add_header("Host", urllibparse.urlparse(url)[1])
		return rq

	def _sid_to_key(self, sid):
		splitter = "."
		l = []
		for item in sid.split(splitter): l.append(item[::-1])
		return splitter.join(l)+self.keysuffix
	def _parse_sid(self):
		if self.api != "web": return "" # ValueError("available only for web API. Now using "+self.api)
		try:
			if self.useProxy:
				old_context = ssl._create_default_https_context
				ssl._create_default_https_context =  ssl.create_default_context
			else:
				old_context = ssl._create_default_https_context
				ssl._create_default_https_context =  ssl._create_unverified_context
			req = self._create_request(self.siteurl)
			req.add_header("User-Agent", self.ua)
			req.add_header("Accept", r"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8 ")
			req.add_header("Accept-Language", r"ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3")
			req.add_header("DNT", "1")
			req.add_header("Accept-Encoding", "gzip")
			response = self._create_opener().open(req).read()
			page = self.decode_response(response)
			#open("page.html", "w", encoding="utf8").write(page)
			try:
				return re.search(r'''SID[\s]?[:][\s]?['"]([^'"]+)['"]''', page).group(1)
			except AttributeError:
				raise YandexFreeTranslateError("blocked or not found")
		except: raise
		finally:
			if self.useProxy:
				ssl._create_default_https_context =  old_context
			else:
				ssl._create_default_https_context =  old_context


	def _save_key(self, key):
		with open(self.keyfilename, "w", encoding="utf8") as f:
			f.write(key)
	def _get_key(self):
		if os.path.isfile(self.keyfilename) and (time.time() - os.path.getmtime(self.keyfilename)) < self.expiretime:
			# print("from file")
			with open(self.keyfilename, "r", encoding="utf8") as f:
				return f.read()
		else:
			# print("from internet")
			sid = self._parse_sid()
			key = self._sid_to_key(sid)
			self._save_key(key)
			return key
	def get_key(self): return self._get_key()
	def regenerate_key(self):
		if os.path.isfile(self.backfilename): os.remove(self.backfilename)
		if os.path.isfile(self.keyfilename):
			os.rename(self.keyfilename, self.backfilename)
		self.key = self._get_key()
		return self.key
	def __init__(self, api="broker1"):
		self.api = api
		if not os.path.isfile(self.keyfilename) and os.path.isfile(self.backfilename):
			os.rename(self.backfilename, self.keyfilename)
	def translate(self, lang, text=""):
		utr = ''
		if self.api == 'broker1':
			utr = self.broker1+"?"+urllibparse.urlencode(self._getparams(lang=lang))
		else:
			utr = self.apibaseurl+"translate?"+urllibparse.urlencode(self._getparams(lang=lang))
		resp = {}
		content = None
		try:
			if self.useProxy:
				old_context = ssl._create_default_https_context
				ssl._create_default_https_context =  ssl.create_default_context
			if self.key == "": self.key = self._get_key()
			if text == "": raise ValueError("text")
			p=[]
			for part in smartsplit(text, 500, 550):
				req = self._create_request(utr)
				req.add_header("User-Agent", self.ua)
				req.add_header("Accept", r"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8 ")
				req.add_header("Accept-Language", r"ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3")
				req.add_header("DNT", "1")
				req.add_header("Accept-Encoding", "gzip, deflate, br")
				try:
					response = self._create_opener().open(req, data = urllibparse.urlencode({
						"text":part
					}).encode("UTF8")).read()
					content = self.decode_response(response)
					resp = json.loads(content)
				except (urlliberror.HTTPError, json.JSONDecodeError):
					if self.error_count >= 2:
						self.error_count = 0
						if sys.exc_info()[0] == json.JSONDecodeError:
							raise YandexFreeTranslateError(content)
						else:
							raise
					else:
						self.error_count = self.error_count + 1
						self.regenerate_key()
						return self.translate(lang, text)
				if "text" not in resp:
					raise YandexFreeTranslateError(content)
				p.append(resp["text"][0])
			resp["text"] = p
			return resp
		except: raise
		finally:
			if self.useProxy:
				ssl._create_default_https_context =  old_context


