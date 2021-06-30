import coloredlogs
# import logging

# Styling
# https://www.programcreek.com/python/example/105258/coloredlogs.DEFAULT_LEVEL_STYLES

coloredlogs.DEFAULT_FIELD_STYLES = {
    'hostname': {'color': 'magenta'},
    'programname': {'color': 'cyan'},
    'name': {'color': 'blue'},
    'levelname': {'color': 'black', 'bold': True},
    'asctime': {'color': 'blue'}}
coloredlogs.DEFAULT_LEVEL_STYLES = {
    'info': {"color": "green"},
    "warning": {"color": "yellow", "bold": True},
    "success": {"color": "green", "bold": True},
    "error": {"color": "red", "bold": True},
}
coloredlogs.install(level='INFO', fmt='%(asctime)s - %(levelname)s - %(name)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')


#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')