# Third-party components

The offline installer includes unmodified Blender 5.2.2 LTS (Windows x64), its embedded Python and libraries, FFmpeg 7.1 essentials (Gyan build), and Three.js 0.180.0.

- Blender: https://www.blender.org/about/license/ . Copyright and full third-party license texts are retained in runtime/blender/copyright.txt and runtime/blender/license/. Matching main source: https://download.blender.org/source/blender-5.2.2.tar.xz . Binary: https://download.blender.org/release/Blender5.2/blender-5.2.2-windows-x64.zip ; official SHA256: 3849d17a682cba006075aaa3f3597ecb5c9c30ec31035b2e092c53e40679b535 .
- FFmpeg: https://ffmpeg.org/legal.html . This static build is GPLv3, with --enable-gpl --enable-version3 and libx264. Its own GPL license and detailed build configuration/source attribution are retained in runtime/ffmpeg/LICENSE and README.txt. Corresponding main source: https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz (upstream commit b08d7969c5). Binary source: https://github.com/GyanD/codexffmpeg/releases/tag/7.1 . These notices do not replace the applicable GPL terms or the source/build requirements of the linked third-party libraries.
- Python and bundled libraries: license notices are kept inside the clean Blender distribution.
- Three.js: MIT, license retained in web/vendor/three/LICENSE.
- NSIS 3.13 installer builder: https://nsis.sourceforge.io/Docs/AppendixI.html (zlib/libpng and component-specific licenses). No installer-builder dependency is needed on the user's machine.

Matching Blender and FFmpeg main source archives and the source/build references accompany the release for inspection. The application source is provided in the public Vantage repository; this file does not change the ownership or separately grant a new license to Vantage code. Redistribution must comply with the applicable terms for Blender-integrated modules and all linked third-party components, including their corresponding-source requirements.

No personal models, scenes, motion files, projects, credentials, or Blender portable preferences are part of the installer. Uninstallation keeps user data and cache outside the installation folder.
