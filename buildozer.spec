[app]
title = AlgoBotPro
package.name = algobotpro
package.domain = com.algobotpro

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,db

version = 1.0.0

requirements = python3,kivy==2.3.0,requests,pillow,sqlite3

orientation = portrait

android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,FOREGROUND_SERVICE

android.api = 33
android.minapi = 21
android.sdk = 33
android.ndk = 25b
android.ndk_api = 21

android.archs = arm64-v8a

android.allow_backup = True
android.internet = True

fullscreen = 0

android.presplash.filename = %(source.dir)s/assets/presplash.png
android.icon.filename = %(source.dir)s/assets/icon.png

[buildozer]
log_level = 2
warn_on_root = 1
