# Yandex.Translate addon for NVDA

[Addon home page](https://github.com/alekssamos/YandexTranslate/)

After installation, go to the **NVDA menu**, **Preferences**, **Input Gestures**,
assign convenient keyboard shortcuts for YandexTranslate. Or use the already pre-installed ones (below).

> Other translators, such as "Translate", "InstantTranslate" and others,
> if there is, it is better to disable or delete it, in order to avoid conflicts.

New 3: added the ability to save translates to the cache. If you need it, check the appropriate box in the add-on settings.

New 2: Starting with the version from October 5, 2021,
by default, requests will go through my server.
This should improve the service for you, since Yandex blocks some IP addresses.
You can always disable this in the settings by changing the API type to web or iOS.

New: If it doesn't work, an error occurred when creating the key or something 
such,
then open the NVDA Menu, Tools, Yandex Translate Settings
and install the API on iOS.
These keys are used in the iPhone app and have not changed for more than 6 months,
it should work better and more stable.

The addon translates the selected text fragment or content from the clipboard, there is an automatic (instant) translation of NVDA speech.

If there is a braille display, the result will be duplicated on it as well.

> Doesn't translate? Set up language pairs.
> Didn't help?
> Change the IP address / reconnect connection to the Internet (turn off turn on the wifi router from the socket),
> turn on or off airplane mode, etc.

The addon can be configured in the NVDA menu, Tools, Yandex Translate Settings.

The use of a proxy server is supported.

It is possible to work with configuration profiles, for example, there is one language pair for the Google Chrome browser, another for Unigram, and in the Notepad program you want to turn on the sound signal during translation. **NVDA menu**, **Configuration profiles...**, for each application you create, 
switch and configure the translator.

### Keyboard shortcuts
* nvda+Shift+T - Translation of the selected text.
* nvda+Shift+Y - Translate text from the clipboard.
* nvda+Shift+U - Swap the primary and secondary target languages.
* nvda+Shift+I - Automatic translation.
* The gesture is not assigned - Translate the last spoken phrase
