Z-GUI — лицензии сторонних компонентов

1. zapret (bol-van/zapret) — MIT
   Copyright (c) bol-van
   Текст: licenses/zapret-discord-youtube-LICENSE.txt (включает уведомление bol-van)
   Источник: https://github.com/bol-van/zapret

2. zapret-discord-youtube (Flowseal) — MIT
   Copyright (c) 2016-2026 bol-van, 2024-2026 Flowseal
   Текст: licenses/zapret-discord-youtube-LICENSE.txt
   Источник: https://github.com/Flowseal/zapret-discord-youtube

3. tg-ws-proxy (Flowseal) — MIT
   Copyright (c) 2026 Flowseal
   Текст: licenses/tg-ws-proxy-LICENSE.txt
   Источник: https://github.com/Flowseal/tg-ws-proxy

4. WinDivert (basil00) — на выбор LGPL-3.0 или GPL-2.0
   В составе zapret распространяются бинарные файлы WinDivert.dll и WinDivert64.sys
   без изменений. Выбрана LGPL-3.0; исходный код доступен по адресу
   https://github.com/basil00/WinDivert
   Текст: licenses/WinDivert-LICENSE.txt

5. cygwin1.dll (Cygwin, Red Hat) — вердикт: совместимо
   Библиотека Cygwin API распространяется по GNU LGPL версии 3 или новее
   с дополнительным исключением для компоновки (Cygwin Linking Exception),
   которое разрешает передавать исполняемые файлы, слинкованные с libcygwin.a,
   на условиях по вашему выбору. Мы передаём cygwin1.dll без изменений,
   рядом с winws.exe, и предоставляем текст лицензии и ссылку на исходники.
   Текст: licenses/cygwin-LICENSE.txt
   Источник: https://cygwin.com/licensing.html
   Исходный код: https://sourceware.org/git/?p=newlib-cygwin.git

6. Python, PySide6 (Qt), pystray, Pillow, psutil, httpx, h2, cryptography, certifi
   Распространяются в составе сборки на условиях соответствующих лицензий:
   PSF-2.0, LGPL-3.0 (Qt/PySide6), LGPL-3.0 (pystray), MIT-CMU (Pillow),
   BSD-3-Clause (psutil), BSD-3-Clause (httpx), MIT (h2), Apache-2.0/BSD (cryptography),
   MPL-2.0 (certifi). Тексты лицензий включены в дистрибутив пакетов.
