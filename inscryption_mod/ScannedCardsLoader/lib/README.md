# lib/

Put `InscryptionAPI.dll` here before building (it is not on a NuGet feed this
project can use, and it is not redistributed in this repository).

Get it from either:

- your game install: `Inscryption/BepInEx/plugins/API_dev-API/InscryptionAPI.dll`
  (Thunderstore / r2modman layout) or `Inscryption/BepInEx/plugins/InscryptionAPI.dll`
  (manual install), or
- the API package: https://thunderstore.io/c/inscryption/p/API_dev/API/ (developed and
  checked against 2.24.1) - the DLL is in its `plugins` folder.

Alternatively build with `-p:InscryptionAPIDir="<folder containing InscryptionAPI.dll>"`.
