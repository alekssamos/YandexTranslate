import scriptHandler
import os
import json
import time
import wx
import threading
import http.client
import sys
import pickle
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
_cache = {}
FILE_CONFIG_PATH = os.path.join(globalVars.appArgs.configPath, "YandexTranslateSettings.pickle")

proxy_protocols = tuple(["http", "https", "socks4", "socks5"])
conf = {
	"key": "",
	"sourceLang": "auto",
	"primaryTargetLang": "en",
	"secondaryTargetLang": "ru",
	"switchLang": "ru",
	"copyToClipBoard": True,
	"signals": False,
	"useProxy": False,
	"proxy_protocol": proxy_protocols[3],
	"proxy_host": "socks.zaborona.help",
	"proxy_port": 1488,
	"proxy_username": "",
	"proxy_password": "",
}
default_conf = conf.copy()

ERRORS = {
	401: _("Invalid API key"),
	402: _("This API key has been blocked"),
	403: _("You have reached the daily limit for requests"),
	404: _("You have reached the daily limit for the volume of translated text"),
	413: _("The text size exceeds the maximum"),
	422: _("The text could not be translated"),
	501: _("The specified translation direction is not supported"),
}

# Decorator to lock the scripts on the secure desktop
def secureScript(script):
	def wrapper(self, gesture):
		if globalVars.appArgs.secure:
			ui.message(_("Action cannot be performed because NVDA running on secure desktop"))
		else:
			script(self, gesture)
	return wrapper

yt = YandexFreeTranslate()
class YandexTranslateSettingsDialog(gui.SettingsDialog):
	title = _("Yandex Translate Settings")

	def makeSettings(self, sizer):
		self.langList = [", ".join((lang, code)) for code, lang in languages.items()]
		self.langList.sort()
		settingsSizerHelper = gui.guiHelper.BoxSizerHelper(self, sizer=sizer)

		self.sourceLang = settingsSizerHelper.addLabeledControl(_("&Source language:"), wx.Choice, choices=[_("&Detect language automatically")+", auto"]+self.langList)
		if conf["sourceLang"] == "auto":
			self.sourceLang.SetSelection(0)
		else:
			self.sourceLang.SetStringSelection(", ".join((languages[conf["sourceLang"]], conf["sourceLang"])))

		self.primaryTargetLang = settingsSizerHelper.addLabeledControl(_("&Primary target language:"), wx.Choice, choices=self.langList)
		self.primaryTargetLang.SetStringSelection(", ".join((languages[conf["primaryTargetLang"]], conf["primaryTargetLang"])))

		self.secondaryTargetLang = settingsSizerHelper.addLabeledControl(_("S&econdary target language:"), wx.Choice, choices=self.langList)
		self.secondaryTargetLang.SetStringSelection(", ".join((languages[conf["secondaryTargetLang"]], conf["secondaryTargetLang"])))

		self.switchLang = settingsSizerHelper.addLabeledControl(_("&Language translation, if the language of the text coincides with the target:"), wx.Choice, choices=self.langList)
		self.switchLang.SetStringSelection(", ".join((languages[conf["switchLang"]], conf["switchLang"])))

		self.copyToClipBoard = wx.CheckBox(self, label=_("&Copy translation to clipboard"))
		self.copyToClipBoard.SetValue(conf["copyToClipBoard"])
		settingsSizerHelper.addItem(self.copyToClipBoard)

		self.signals = wx.CheckBox(self, label=_("&Play tones when translation waiting"))
		self.signals.SetValue(conf["signals"])
		settingsSizerHelper.addItem(self.signals)

		# self.key = settingsSizerHelper.addLabeledControl(_("&API key:"), wx.TextCtrl, value=conf["key"])

		self.generate_new_key = wx.Button(self, label=_("&Generate new API key"))
		self.generate_new_key.Bind(wx.EVT_BUTTON, self.onGenerate_new_key)
		settingsSizerHelper.addItem(self.generate_new_key)

		self.useProxy = wx.CheckBox(self, label=_("&Use proxy server"))
		self.useProxy.SetValue(conf["useProxy"])
		self.useProxy.Bind(wx.EVT_CHECKBOX, self.onUseProxy)
		settingsSizerHelper.addItem(self.useProxy)

		self.proxy_protocol = settingsSizerHelper.addLabeledControl(_("Proxy &protocol:"), wx.Choice, choices=proxy_protocols)
		self.proxy_protocol.SetStringSelection(conf["proxy_protocol"])

		self.proxy_host = settingsSizerHelper.addLabeledControl(_("Proxy &host:"), wx.TextCtrl, value=conf["proxy_host"])
		self.proxy_port = settingsSizerHelper.addLabeledControl(_("Proxy p&ort:"), wx.SpinCtrl, value=str(conf["proxy_port"]))
		self.proxy_port.SetRange(1, 65535)
		self.proxy_username = settingsSizerHelper.addLabeledControl(_("Proxy &login:"), wx.TextCtrl, value=conf["proxy_username"])
		self.proxy_password = settingsSizerHelper.addLabeledControl(_("Proxy p&assword:"), wx.TextCtrl, value=conf["proxy_password"],
			style=wx.TE_PASSWORD)

		self.reset_settings = wx.Button(self, label=_("&Reset settings to the default value"))
		self.reset_settings.Bind(wx.EVT_BUTTON, self.onReset)
		settingsSizerHelper.addItem(self.reset_settings)

	def postInit(self):
		self.sourceLang.SetFocus()
		self.onUseProxy(None)

	def onGenerate_new_key(self, event):
		try:
			conf["key"] = yt.regenerate_key()
			gui.messageBox(_("A new key is created successfully")+"\n"+conf["key"], "", style=wx.OK | wx.ICON_INFORMATION)
		except Exception as identifier:
			text = _("Failed to get a new key. Check your internet connection, wait a bit or go to Yandex, enter the captcha and try again.")
			ui.message(text)
			log.debug(sys.exc_info()[1])
			gui.messageBox(text, _("Error saving settings"), style=wx.OK | wx.ICON_ERROR)
			import webbrowser
			webbrowser.open_new("https://translate.yandex.ru/")

	def onUseProxy(self, event):
		items = frozenset([self.proxy_host, self.proxy_password, self.proxy_port, self.proxy_protocol, self.proxy_username])
		if self.useProxy.Value:
			for elem in items: elem.Enable()
		else:
			for elem in items: elem.Disable()

	def _save_settings(self):
		try:
			with open(FILE_CONFIG_PATH, "wb") as fileConfig:
				pickle.dump(conf, fileConfig, pickle.HIGHEST_PROTOCOL)
		except (IOError, OSError) as e:
			gui.messageBox(e.strerror, _("Error saving settings"), style=wx.OK | wx.ICON_ERROR)

	def onReset(self, event):
		global conf, default_conf
		conf = default_conf.copy()
		self._save_settings()
		self.Close()

	def onOk(self, event):
		conf["sourceLang"] = self.sourceLang.GetStringSelection().split()[-1]
		conf["primaryTargetLang"] = self.primaryTargetLang.GetStringSelection().split()[-1]
		conf["secondaryTargetLang"] = self.secondaryTargetLang.GetStringSelection().split()[-1]
		conf["switchLang"] = self.switchLang.GetStringSelection().split()[-1]
		conf["copyToClipBoard"] = self.copyToClipBoard.Value
		conf["signals"] = self.signals.Value
		conf["useProxy"] = self.useProxy.Value
		if self.useProxy.Value:
			conf["proxy_protocol"] = self.proxy_protocol.GetStringSelection().split()[-1]
			conf["proxy_host"] = self.proxy_host.Value.strip()
			conf["proxy_port"] = self.proxy_port.Value
			conf["proxy_username"] = self.proxy_username.Value.strip()
			conf["proxy_password"] = self.proxy_password.Value.strip()
		self._save_settings()
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
		if conf["signals"]:
			self._beeper = Beeper()

		if isinstance(self._kwargs["text"], str):
			self._kwargs["text"] = [self._kwargs["text"]]

		self._kwargs["text"] = [s.encode("utf-8") for s in self._kwargs["text"]]
		self._kwargs["text"] = tuple(self._kwargs["text"])

		status, request = self._HTTPRequest()

		if status:
			sourceLang, targetLang = request["lang"].split("-")
			if self._useLangSwitch and sourceLang == targetLang != conf["switchLang"]:
				self._kwargs["lang"] = "-".join((sourceLang, conf["switchLang"]))
				status, request = self._HTTPRequest()

		if self._beeper:
			self._beeper.stop()
		wx.CallAfter(self._callback, status, request)

	def _dc(self, s): return s.decode("UTF8")

	def _HTTPRequest(self):
		cacheKey = (self._kwargs["lang"], self._kwargs["text"])
		if cacheKey in _cache:
			log.debug("cache: True")
			return True, _cache[cacheKey]

		if conf["useProxy"]:
			yt.setProxy(conf["proxy_protocol"],
				conf["proxy_host"], conf["proxy_port"], conf["proxy_username"], conf["proxy_password"])
		try:
			responseData = yt.translate(self._kwargs["lang"], "\n".join(list(map(self._dc, self._kwargs["text"]))))
		except Exception as e:
			return False, e

		responseCode = responseData["code"]
		if responseCode != 200:
			return False, responseCode

		_cache[cacheKey] = responseData
		return True, responseData

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Yandex Translate")

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		if globalVars.appArgs.secure: return

		self.llastTranslatedText = None
		self.targetLang = "primaryTargetLang"
		self.autoTranslate = False
		speech.speak = self.speakDecorator(speech.speak)

		if languageHandler.getLanguage() in languages:
			conf["primaryTargetLang"] = languageHandler.getLanguage()

		try:
			with open(FILE_CONFIG_PATH, "rb") as fileConfig:
				conf.update(pickle.load(fileConfig))
		except Exception:
			pass

		try:
			if conf["key"] == "": conf["key"] = yt.get_key()
		except Exception as identifier:
			pass

		# Creates submenu of addon
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU,
			lambda e: gui.mainFrame._popupSettingsDialog(YandexTranslateSettingsDialog),
			gui.mainFrame.sysTrayIcon.toolsMenu.Append(wx.ID_ANY, _("Yandex Translate Settings...")))

	def speakDecorator(self, speak):
		def wrapper(speechSequence, *args, **kwargs):
			self.speechSequence = speechSequence
			if not self.autoTranslate:
				return speak(speechSequence, *args, **kwargs)
			def autoTranslateHandler(status, request):
				if not status:
					return speak(speechSequence, *args, **kwargs)
				translatedSpeechSequence = []
				t = [s for s in request["text"]] # need copy of the list
				for item in speechSequence:
					if isinstance(item, str):
						try: translatedSpeechSequence.append(t.pop(0))
						except IndexError: pass
					else:
						translatedSpeechSequence.append(item)
				return speak(translatedSpeechSequence, *args, **kwargs)
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

		if conf["copyToClipBoard"]:
			api.copyToClip(self.llastTranslatedText)

	def getLang(self):
		if conf["sourceLang"] == "auto":
			return conf[self.targetLang]
		return conf["sourceLang"] + "-" + conf[self.targetLang]

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
		ui.message(languages[conf[self.targetLang]])

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
