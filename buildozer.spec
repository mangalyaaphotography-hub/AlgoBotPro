[app]
title = AlgoBotPro
package.name = algobotpro
package.domain = com.algobotpro

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0.0

requirements = python3,kivy==2.3.0,requests,pillow

orientation = portrait

android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.build_tools_version = 33.0.2
android.accept_sdk_license = True
android.archs = arm64-v8a
android.allow_backup = True

android.presplash.filename = %(source.dir)s/assets/presplash.png
android.icon.filename = %(source.dir)s/assets/icon.png

fullscreen = 0

[buildozer]
log_level = 2
warn_on_root = 0
