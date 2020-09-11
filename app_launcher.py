from sys import argv, exit
from signal import signal, SIGINT
from multiprocessing import Process, freeze_support
from os import execv
import platform


app_list = argv[1] if len(argv) > 1 else "apps.txt"
appv = []

def stop_apps(signal, frame):
	for app in appv:
		print(f"stopping {app['hostname']}")
		app['process'].terminate()
	exit(0)

signal(SIGINT, stop_apps)


def launch_app(host):
	if platform.system() == 'Linux':
		execv("launch_csp.sh", ['launch_csp.sh', host])
	elif platform.system() == 'Windows':
		execv("launch_csp.bat", ['launch_csp.bat', host])

if __name__ == '__main__':
	with open(app_list) as apps:
		for app_info in apps:
			hostname = app_info.rstrip()
			appv.append({'hostname':hostname, 'process':Process(target=launch_app, args=(hostname,))})

for app in appv:
	print(f"starting {app['hostname']}")
	app['process'].start()

