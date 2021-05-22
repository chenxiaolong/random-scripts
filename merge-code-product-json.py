import json

PATH_CODE_MSFT = '/usr/share/code/resources/app/product.json'
PATH_CODE_OSS = '/usr/share/code-oss/resources/app/product.json'

# Other candidates
# - auth
# - configurationSync.store
# - extensionSyncedKeys
# - linkProtectionTrustedDomains
# - settingsSearchUrl
# - webEndpointUrl
WANTED_KEYS = [
    'configBasedExtensionTips',
    'exeBasedExtensionTips',
    'extensionAllowedBadgeProviders',
    'extensionAllowedBadgeProvidersRegex',
    'extensionAllowedProposedApi',
    'extensionImportantTips',
    'extensionKeywords',
    'extensionKind',
    'extensionsGallery',
    'extensionTips',
    'keymapExtensionTips',
    'remoteExtensionTips',
]
BLACKLISTED_KEYS = [
    'extensionSyncedKeys',
]

def main():
    with open(PATH_CODE_MSFT) as f:
        data_msft = json.load(f)
    with open(PATH_CODE_OSS) as f:
        data_oss = json.load(f)

    # Check if there are any new keys not accounted for
    for key in data_msft:
        if key not in WANTED_KEYS and key not in BLACKLISTED_KEYS and \
                (key.startswith('extension') or key.endswith('Tips')):
            raise ValueError(f'{key} might be a useful key')

    for key in WANTED_KEYS:
        if key in data_oss:
            print(f'{key} already exists in OSS product.json')

        data_oss[key] = data_msft[key]

    with open(PATH_CODE_OSS, 'w') as f:
        json.dump(data_oss, f, indent=4)

if __name__ == '__main__':
    main()
