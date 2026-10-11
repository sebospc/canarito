#!/bin/sh
# Archive, check entitlements, upload to TestFlight. Raise CURRENT_PROJECT_VERSION in project.yml first.
# Why the ad-hoc codesign: automatic signing of the archive needs a registered device (the team has none),
# and CODE_SIGNING_ALLOWED=NO leaves the binary without entitlements, so iOS refuses push ("no valid
# aps-environment"). Export re-signs with the distribution profile but keeps the entitlements it finds.
set -eu
cd "$(dirname "$0")/.."
# Your App Store Connect API key (Users and Access, Integrations): its id and issuer id.
KEY_ID=${ASC_KEY_ID:?set ASC_KEY_ID}
ISSUER=${ASC_ISSUER_ID:?set ASC_ISSUER_ID}
KEY="$HOME/.appstoreconnect/private_keys/AuthKey_$KEY_ID.p8"
W=/private/tmp/canarito-arch
rm -rf "$W"; mkdir -p "$W"
AUTH="-allowProvisioningUpdates -authenticationKeyPath $KEY -authenticationKeyID $KEY_ID -authenticationKeyIssuerID $ISSUER"

xcodebuild -project Canarito.xcodeproj -scheme Canarito -configuration Release -destination 'generic/platform=iOS' \
  -archivePath "$W/C.xcarchive" -derivedDataPath "$W/dd" archive CODE_SIGNING_ALLOWED=NO | tail -1
sed 's/\$(APS_ENVIRONMENT)/production/' Canarito/Canarito.entitlements > "$W/ent.plist"
codesign -f -s - --entitlements "$W/ent.plist" "$W/C.xcarchive/Products/Applications/Canarito.app"

cat > "$W/export.plist" <<P
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0"><dict>
<key>method</key><string>app-store-connect</string><key>destination</key><string>export</string>
<key>teamID</key><string>BGKJDXR2L4</string><key>signingStyle</key><string>automatic</string>
</dict></plist>
P
xcodebuild -exportArchive -archivePath "$W/C.xcarchive" -exportOptionsPlist "$W/export.plist" -exportPath "$W/out" $AUTH | tail -1

unzip -q "$W/out/Canarito.ipa" -d "$W/ipa"
ENT=$(codesign -d --entitlements - "$W/ipa/Payload/Canarito.app" 2>&1)
echo "$ENT" | grep -A2 'aps-environment' | grep -q '\[String\] production' || { echo "STOP: aps-environment is not production"; exit 1; }
echo "$ENT" | grep -q 'usernotifications.time-sensitive' || { echo "STOP: time-sensitive missing"; exit 1; }
echo "entitlements ok"

sed -i '' 's#<string>export</string>#<string>upload</string>#' "$W/export.plist"
xcodebuild -exportArchive -archivePath "$W/C.xcarchive" -exportOptionsPlist "$W/export.plist" -exportPath "$W/up" $AUTH | grep -E "Upload succeeded|EXPORT"
rm -rf "$W"
