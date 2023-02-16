import schedule
import time
from get_resources import grab_data
import global_variables as var

# Initialize variables
var.init()  

GLAB_PROJECT_OWNERSHIP=var.GLAB_PROJECT_OWNERSHIP
GLAB_PROJECT_VISIBILITY=var.GLAB_PROJECT_VISIBILITY
gl = var.gl
endpoint= var.endpoint
headers=var.headers
   
def send_to_nr():
    projects = gl.projects.list(owned=GLAB_PROJECT_OWNERSHIP,visibility=GLAB_PROJECT_VISIBILITY,get_all=True)
    try:
        for project in projects:
            grab_data(project)
        print('Exporter finished!!!')
    except Exception as e:
        print(e)


if var.GLAB_STANDALONE:
    # Run once, then schedule every GLAB_EXPORT_LAST_MINUTES
    send_to_nr()
    time.sleep(1)
    schedule.every(int(var.GLAB_EXPORT_LAST_MINUTES)).minutes.do(send_to_nr) 
    while 1:
        n = schedule.idle_seconds()
        if n is None:
            # no more jobs
            break
        elif n > 0:
            # sleep exactly the right amount of time
            print("Next job run in " + str(round(int(n)/60)) + " minutes")
            time.sleep(n)
        schedule.run_pending()
else:
    send_to_nr()
    