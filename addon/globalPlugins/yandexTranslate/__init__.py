import config
import braille
import scriptHandler
import os
import json
import time
import wx
import threading
import http.client
import sys
from urllib.parse import urlencode

import globalPluginHandler
import gui
import globalVars
import speech
import api
import textInfos
import tones
import ui
import addonHandler
import languageHandler
from logHandler import log

from .languages import languages

from .yandexfreetranslate import YandexFreeTranslate

addonHandler.initTranslation()
if "YandexTranslate" not in config.conf: config.conf["YandexTranslate"]={}
_cache = {}

proxy_protocols = tuple(["http", "https", "socks4", "socks5"])
default_conf = {
	"key": "",
	"api": "broker1",
	"sourceLang": "auto",
	"primaryTargetLang": "en",
	"secondaryTargetLang": "ru",
	"switchLang": "ru",
	"copyToClipBoard": True,
	"signals": False,
	"useCache": False,
	"useProxy": False,
	"proxy_protocol": proxy_protocols[3],
	"proxy_host": "socks.zaborona.help",
	"proxy_port": 1488,
	"proxy_username": "",
	"proxy_password": "",
}

for t in default_conf:
	if t not in config.conf["YandexTranslate"]:
		config.conf["YandexTranslate"][t] = default_conf[t]

FILE_CONFIG_PATH = os.path.join(globalVars.appArgs.configPath, "YandexTranslateSettings.pickle")
if os.path.isfile(FILE_CONFIG_PATH):
	import pickle
	old_conf = {}
	try:
		with open(FILE_CONFIG_PATH, "rb") as fileConfig:
			old_conf.update(pickle.load(fileConfig))
			for t in old_conf:
				if t not in config.conf["YandexTranslate"]:
					config.conf["YandexTranslate"][t] = old_conf[t]
		os.remove(FILE_CONFIG_PATH)
	except:
		pass

ERRORS = {
	401: _("Invalid API key"),
	402: _("This API key has been blocked"),
	403: _("You have reached the daily limit for requests"),
	404: _("You have reached the daily limit for the volume of translated text"),
	413: _("The text size exceeds the maximum"),
	422: _("The text could not be translated"),
	501: _("The specified translation direction is not supported"),
}
def tobool(s):
	if s == "True" or s == "on" or str(s) == "1" or s == "yes": return True
	if s == "False" or s == "off" or str(s) == "0" or s == "no": return False
	return not not s

# Decorator to lock the scripts on the secure desktop
def secureScript(script):
	def wrapper(self, gesture):
		if globalVars.appArgs.secure:
			ui.message(_("Action cannot be performed because NVDA running on secure desktop"))
		else:
			script(self, gesture)
	return wrapper

cacheFile = os.path.join(globalVars.appArgs.configPath, "YandexTranslateCache.json")
if tobool(config.conf["YandexTranslate"]["useCache"]):
	try:
		with open(cacheFile, "rb") as f:
			_cache = json.load(f)
	except Exception as e:
		log.debug(e)

class YandexTranslateSettingsDialog(gui.SettingsDialog):
	title = _("Yandex Translate Settings")

	def makeSettings(self, sizer):
		ytc = config.conf["YandexTranslate"].copy()
		self.langList = [", ".join((lang, code)) for code, lang in languages.items()]
		self.langList.sort()
		settingsSizerHelper = gui.guiHelper.BoxSizerHelper(self, sizer=sizer)

		self.apiSel = settingsSizerHelper.addLabeledControl(_("&API:"), wx.Choice, choices=["Web", "iOS", "broker1"])
		self.apiSel.SetStringSelection(ytc["api"].lower())
		self.Bind(wx.EVT_CHOICE, self.onApiSel)

		self.sourceLang = settingsSizerHelper.addLabeledControl(_("&Source language:"), wx.Choice, choices=[_("&Detect language automatically")+", auto"]+self.langList)
		if ytc["sourceLang"] == "auto":
			self.sourceLang.SetSelection(0)
		else:
			self.sourceLang.SetStringSelection(", ".join((languages[ytc["sourceLang"]], ytc["sourceLang"])))

		self.primaryTargetLang = settingsSizerHelper.addLabeledControl(_("&Primary target language:"), wx.Choice, choices=self.langList)
		self.primaryTargetLang.SetStringSelection(", ".join((languages[ytc["primaryTargetLang"]], ytc["primaryTargetLang"])))

		self.secondaryTargetLang = settingsSizerHelper.addLabeledControl(_("S&econdary target language:"), wx.Choice, choices=self.langList)
		self.secondaryTargetLang.SetStringSelection(", ".join((languages[ytc["secondaryTargetLang"]], ytc["secondaryTargetLang"])))

		self.switchLang = settingsSizerHelper.addLabeledControl(_("&Language translation, if the language of the text coincides with the target:"), wx.Choice, choices=self.langList)
		self.switchLang.SetStringSelection(", ".join((languages[ytc["switchLang"]], ytc["switchLang"])))

		self.copyToClipBoard = wx.CheckBox(self, label=_("&Copy translation to clipboard"))
		self.copyToClipBoard.SetValue(tobool(ytc["copyToClipBoard"]))
		settingsSizerHelper.addItem(self.copyToClipBoard)

		self.signals = wx.CheckBox(self, label=_("&Play tones when translation waiting"))
		self.signals.SetValue(tobool(ytc["signals"]))
		settingsSizerHelper.addItem(self.signals)

		# self.key = settingsSizerHelper.addLabeledControl(_("&API key:"), wx.TextCtrl, value=ytc["key"])

		self.generate_new_key = wx.Button(self, label=_("&Generate new API key"))
		self.generate_new_key.Bind(wx.EVT_BUTTON, self.onGenerate_new_key)
		settingsSizerHelper.addItem(self.generate_new_key)

		self.useCache = wx.CheckBox(self, label=_("&Enable translation caching"))
		self.useCache.SetValue(tobool(ytc["useCache"]))
		settingsSizerHelper.addItem(self.useCache)

		self.clear_cache = wx.Button(self, label=_("Cle&ar the translation cache"))
		self.clear_cache.Bind(wx.EVT_BUTTON, self.onClear_cache)
		settingsSizerHelper.addItem(self.clear_cache)

		self.useProxy = wx.CheckBox(self, label=_("&Use proxy server"))
		self.useProxy.SetValue(tobool(ytc["useProxy"]))
		self.useProxy.Bind(wx.EVT_CHECKBOX, self.onUseProxy)
		settingsSizerHelper.addItem(self.useProxy)

		self.proxy_protocol = settingsSizerHelper.addLabeledControl(_("Proxy &protocol:"), wx.Choice, choices=proxy_protocols)
		self.proxy_protocol.SetStringSelection(ytc["proxy_protocol"])

		self.proxy_host = settingsSizerHelper.addLabeledControl(_("Proxy &host:"), wx.TextCtrl, value=ytc["proxy_host"])
		self.proxy_port = settingsSizerHelper.addLabeledControl(_("Proxy p&ort:"), wx.SpinCtrl, value=str(ytc["proxy_port"]))
		self.proxy_port.SetRange(1, 65535)
		self.proxy_username = settingsSizerHelper.addLabeledControl(_("Proxy &login:"), wx.TextCtrl, value=ytc["proxy_username"])
		self.proxy_password = settingsSizerHelper.addLabeledControl(_("Proxy p&assword:"), wx.TextCtrl, value=ytc["proxy_password"],
			style=wx.TE_PASSWORD)

		self.reset_settings = wx.Button(self, label=_("&Reset settings to the default value"))
		self.reset_settings.Bind(wx.EVT_BUTTON, self.onReset)
		settingsSizerHelper.addItem(self.reset_settings)

	def postInit(self):
		self.onApiSel(None)
		self.apiSel.SetFocus()
		self.onUseProxy(None)

	def onApiSel(self, event):
		global yt
		apitype = self.apiSel.GetStringSelection().lower()
		if apitype == "web":
			self.generate_new_key.Enable()
		elif apitype == "ios":
			self.generate_new_key.Disable()
		else:
			self.generate_new_key.Disable()
			self.useProxy.SetValue(False)
		self.onUseProxy(None)
		yt = YandexFreeTranslate(config.conf["YandexTranslate"]["api"].lower())

	def onGenerate_new_key(self, event):
		yt = YandexFreeTranslate(config.conf["YandexTranslate"]["api"].lower())
		try:
			config.conf["YandexTranslate"]["key"] = yt.regenerate_key()
			gui.messageBox(_("A new key is created successfully")+"\n"+config.conf["YandexTranslate"]["key"], "", style=wx.OK | wx.ICON_INFORMATION)
		except Exception as identifier:
			text = _("Failed to get a new key. Check your internet connection, wait a bit or go to Yandex, enter the captcha and try again.")
			ui.message(text)
			log.debug(sys.exc_info()[1])
			gui.messageBox(text, _("Error saving settings"), style=wx.OK | wx.ICON_ERROR)
			import webbrowser
			webbrowser.open_new("https://translate.yandex.ru/")

	def onClear_cache(self, event):
		global _cache
		_cache = {}
		with open(cacheFile, "w", encoding="UTF-8") as fp:
			json.dump({}, fp)
			os.fsync(fp)
		ui.message(_("Cache cleared successfully"))

	def onUseProxy(self, event):
		items = frozenset([self.proxy_host, self.proxy_password, self.proxy_port, self.proxy_protocol, self.proxy_username])
		if self.useProxy.Value:
			for elem in items: elem.Enable()
		else:
			for elem in items: elem.Disable()

	def _save_settings(self):
		try:
			# config.conf.save();
			pass
		except (IOError, OSError) as e:
			gui.messageBox(e.strerror, _("Error saving settings"), style=wx.OK | wx.ICON_ERROR)

	def onReset(self, event):
		config.conf["YandexTranslate"] = default_conf.copy()
		# self._save_settings()
		self.Close()

	def onOk(self, event):
		config.conf["YandexTranslate"]["api"] = self.apiSel.GetStringSelection().lower()
		config.conf["YandexTranslate"]["sourceLang"] = self.sourceLang.GetStringSelection().split(", ")[-1]
		config.conf["YandexTranslate"]["primaryTargetLang"] = self.primaryTargetLang.GetStringSelection().split(", ")[-1]
		config.conf["YandexTranslate"]["secondaryTargetLang"] = self.secondaryTargetLang.GetStringSelection().split(", ")[-1]
		config.conf["YandexTranslate"]["switchLang"] = self.switchLang.GetStringSelection().split(", ")[-1]
		config.conf["YandexTranslate"]["copyToClipBoard"] = self.copyToClipBoard.Value
		config.conf["YandexTranslate"]["signals"] = self.signals.Value
		config.conf["YandexTranslate"]["useCache"] = self.useCache.Value
		config.conf["YandexTranslate"]["useProxy"] = self.useProxy.Value
		if self.useProxy.Value:
			config.conf["YandexTranslate"]["proxy_protocol"] = self.proxy_protocol.GetStringSelection().split(", ")[-1]
			config.conf["YandexTranslate"]["proxy_host"] = self.proxy_host.Value.strip()
			config.conf["YandexTranslate"]["proxy_port"] = self.proxy_port.Value
			config.conf["YandexTranslate"]["proxy_username"] = self.proxy_username.Value.strip()
			config.conf["YandexTranslate"]["proxy_password"] = self.proxy_password.Value.strip()
		# self._save_settings()
		super(YandexTranslateSettingsDialog, self).onOk(event)

class Beeper(threading.Thread):

	def __init__(self):
		super(Beeper, self).__init__()
		self.daemon = True
		self._mutex = threading.Lock()
		self.start()

	def run(self):
		while True:
			time.sleep(1)
			if self._mutex.locked():
				return
			tones.beep(500, 100)
			time.sleep(0.1)

	def stop(self):
		self._mutex.acquire()

class YandexTranslate(threading.Thread):

	def __init__(self, callback, useLangSwitch=True, **kwargs):
		super(YandexTranslate, self).__init__()
		self._callback = callback
		self._kwargs = kwargs
		self._beeper = None
		self._useLangSwitch = useLangSwitch
		self.daemon = True
		self.start()

	def run(self):
		ytc = config.conf["YandexTranslate"].copy()
		if tobool(ytc["signals"]):
			self._beeper = Beeper()

		if isinstance(self._kwargs["text"], str):
			self._kwargs["text"] = [self._kwargs["text"]]

		self._kwargs["text"] = [s.encode("utf-8") for s in self._kwargs["text"]]
		self._kwargs["text"] = tuple(self._kwargs["text"])

		status, request = self._HTTPRequest()

		if status:
			sourceLang, targetLang = request["lang"].split("-")
			if self._useLangSwitch and sourceLang == targetLang != ytc["switchLang"]:
				self._kwargs["lang"] = "-".join((sourceLang, ytc["switchLang"]))
				status, request = self._HTTPRequest()

		if self._beeper:
			self._beeper.stop()
		wx.CallAfter(self._callback, status, request)

	def _dc(self, s): return s.decode("UTF8")

	def _HTTPRequest(self):
		global _cache
		yt = YandexFreeTranslate(config.conf["YandexTranslate"]["api"].lower())
		cacheKey = str(self._kwargs["lang"]) + str(self._kwargs["text"])
		if cacheKey in _cache:
			log.debug("cache: True")
			return True, _cache[cacheKey]

		if tobool(config.conf["YandexTranslate"]["useProxy"]):
			yt.setProxy(config.conf["YandexTranslate"]["proxy_protocol"],
				config.conf["YandexTranslate"]["proxy_host"], config.conf["YandexTranslate"]["proxy_port"], config.conf["YandexTranslate"]["proxy_username"], config.conf["YandexTranslate"]["proxy_password"])
		try:
			responseData = yt.translate(self._kwargs["lang"], "\n".join(list(map(self._dc, self._kwargs["text"]))))
		except Exception as e:
			return False, e

		responseCode = responseData["code"]
		if responseCode != 200:
			return False, responseCode

		_cache[cacheKey] = responseData
		if tobool(config.conf["YandexTranslate"]["useCache"]):
			try:
				with open(cacheFile, "w", encoding="UTF-8") as fp:
					json.dump(_cache, fp)
					os.fsync(fp)
			except Exception as e:
				log.debug(e)
		return True, responseData

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Yandex Translate")

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		if globalVars.appArgs.secure: return

		self.llastTranslatedText = None
		self.autoTranslate = False
		self.targetLang = "primaryTargetLang"

		try:
			speech.speech.speak = self.speakDecorator(speech.speech.speak)
		except:
			speech.speak = self.speakDecorator(speech.speak)
		try:
			try:
				speech.sayAll.SayAllHandler.speechWithoutPausesInstance.speak = speech.speech.speak
			except AttributeError:
				speech.speakWithoutPauses=speech.SpeechWithoutPauses(speakFunc=speech.speak).speakWithoutPauses
		except:
			pass

		try:
			if config.conf["YandexTranslate"]["key"] == "": config.conf["YandexTranslate"]["key"] = yt.get_key()
		except Exception as identifier:
			pass

		# Creates submenu of addon
		self.YandexTranslateSettingsItem = gui.mainFrame.sysTrayIcon.toolsMenu.Append(wx.ID_ANY, _("Yandex Translate Settings..."))
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU,
			lambda e: gui.mainFrame._popupSettingsDialog(YandexTranslateSettingsDialog),
			self.YandexTranslateSettingsItem)

	def terminate(self):
		try:
			gui.mainFrame.sysTrayIcon.toolsMenu.RemoveItem(
				self.YandexTranslateSettingsItem)
		except:
			pass

	def speakDecorator(self, speak):
		def my_speak(speechSequence, *args, **kwargs):
			try: braille.handler.message(" ".join(speechSequence))
			except: pass
			return speak(speechSequence, *args, **kwargs)
		def wrapper(speechSequence, *args, **kwargs):
			self.speechSequence = speechSequence
			if not self.autoTranslate:
				return speak(speechSequence, *args, **kwargs)
			def autoTranslateHandler(status, request):
				if not status:
					return my_speak(speechSequence, *args, **kwargs)
				translatedSpeechSequence = []
				t = [s for s in request["text"]] # need copy of the list
				for item in speechSequence:
					if isinstance(item, str):
						try: translatedSpeechSequence.append(t.pop(0))
						except IndexError: pass
					else:
						translatedSpeechSequence.append(item)
				return my_speak(translatedSpeechSequence, *args, **kwargs)
			YandexTranslate(autoTranslateHandler, useLangSwitch=False, text=[s for s in speechSequence if isinstance(s, str)], lang=self.getLang())
		return wrapper

	def errorHandler(self, msg):
		if isinstance(msg, Exception):
			text = _("Unfortunately the translation is not available. Please check your Internet connection")
		else:
			text = ERRORS.get(msg)

		if text is None:
			text = _("Error: %s") % msg

		ui.message(text)
		log.error(msg)

	def translateHandler(self, status, request):
		if not status:
			self.errorHandler(request)
			return

		self.llastTranslatedText = "\n".join(request["text"])
		ui.message(self.llastTranslatedText)

		if tobool(config.conf["YandexTranslate"]["copyToClipBoard"]):
			api.copyToClip(self.llastTranslatedText)

	def getLang(self):
		if config.conf["YandexTranslate"]["sourceLang"] == "auto":
			return config.conf["YandexTranslate"][self.targetLang]
		return config.conf["YandexTranslate"]["sourceLang"] + "-" + config.conf["YandexTranslate"][self.targetLang]

	def getSelectedText(self):
		obj = api.getCaretObject()
		try:
			info = obj.makeTextInfo(textInfos.POSITION_SELECTION)
			if info or not info.isCollapsed:
				return info.text
		except (RuntimeError, NotImplementedError):
			return None

	@scriptHandler.script(
		description=_("Translate text from the clipboard"),
		gesture="kb:NVDA+shift+Y"
	)
	def script_translate_clip(self, gesture): return self._script_translate_clip(gesture)
	@secureScript
	def _script_translate_clip(self, gesture):
		try:
			text = api.getClipData()
		except Exception:
			ui.message(_("No text to translate"))
			return

		YandexTranslate(self.translateHandler, text=text, lang=self.getLang())

	@scriptHandler.script(
		description=_("Translates the selected text."),
		gesture="kb:NVDA+shift+T"
	)
	def script_translate_sel(self, gesture): return self._script_translate_sel(gesture)
	@secureScript
	def _script_translate_sel(self, gesture):
		text = self.getSelectedText()
		if not text:
			ui.message(_("No text to translate"))
			return

		YandexTranslate(self.translateHandler, text=text, lang=self.getLang())

	@scriptHandler.script(
		description=_("Translates the last spoken phrase")
	)
	def script_translateSpokenPhrase(self, gesture): return self._script_translateSpokenPhrase(gesture)
	@secureScript
	def _script_translateSpokenPhrase(self, gesture):
		text = "\n".join([i for i in self.speechSequence if isinstance(i, str)])

		YandexTranslate(self.translateHandler, text=text, lang=self.getLang())

	@scriptHandler.script(
		description=_("Translates text from navigator object")
	)
	def script_translateNavigatorObject(self, gesture): return self._script_translateNavigatorObject(gesture)
	@secureScript
	def _script_translateNavigatorObject(self, gesture):
		obj = api.getNavigatorObject()
		text = obj.name

		if not text:
			try:
				text = obj.makeTextInfo(textInfos.POSITION_ALL).clipboardText
				if not text: raise RuntimeError()
			except (RuntimeError, NotImplementedError):
				ui.message(_("No text to translate"))
				return

		YandexTranslate(self.translateHandler, text=text, lang=self.getLang())

	@scriptHandler.script(
		description=_("Switching between the primary and secondary target language"),
		gesture="kb:NVDA+shift+U"
	)
	def script_switchTargetLang(self, gesture): return self._script_switchTargetLang(gesture)
	@secureScript
	def _script_switchTargetLang(self, gesture):
		if self.targetLang == "primaryTargetLang":
			self.targetLang = "secondaryTargetLang"
		else:
			self.targetLang = "primaryTargetLang"
		ui.message(languages[config.conf["YandexTranslate"][self.targetLang]])

	@scriptHandler.script(
		description=_("Switching between the primary and secondary target language"),
	)
	def script_copyLlastTranslatedText(self, gesture): return self._script_copyLlastTranslatedText(gesture)
	@secureScript
	def _script_copyLlastTranslatedText(self, gesture):
		if self.llastTranslatedText:
			api.copyToClip(self.llastTranslatedText)
			ui.message(_("Copy to clipboard"))
		else:
			ui.message(_("No translation to copy"))
	script_copyLlastTranslatedText.__doc__ = _("Copy last translation to clipboard")

	@secureScript
	def script_showSettingsDialog(self, gesture):
		gui.mainFrame._popupSettingsDialog(YandexTranslateSettingsDialog)
	script_showSettingsDialog.__doc__ = _("Shows the settings dialog")

	@scriptHandler.script(
		description=_("Switches the function of automatic translation"),
		gesture="kb:NVDA+shift+I"
	)
	def script_switchAutoTranslate(self, gesture):
		if not self.autoTranslate:
			ui.message(_("Automatic translation enabled"))
			self.autoTranslate = True
		else:
			self.autoTranslate = False
			ui.message(_("Automatic translation disabled"))
