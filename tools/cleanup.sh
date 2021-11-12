# Remove templates
rm -rf ./gentools/ansible
find ../ansible/roles -mindepth 1 -maxdepth 1 -type d -not -name "aws" -not -name "azure" -exec rm -rf {} +

# Remove handlers
find ../ansible/*.yaml -delete

# Remove compressed packages
find .. -type f -name "*.zip" -delete

