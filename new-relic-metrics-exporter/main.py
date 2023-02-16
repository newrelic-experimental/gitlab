import schedule
import time
from get_resources import grab_data
import global_variables as var
from multiprocessing import Process
import threading

GLAB_PROJECT_OWNERSHIP=var.GLAB_PROJECT_OWNERSHIP
GLAB_PROJECT_VISIBILITY=var.GLAB_PROJECT_VISIBILITY
gl = var.gl
endpoint= var.endpoint
headers=var.headers

def send_to_nr():
    projects = gl.projects.list(owned=GLAB_PROJECT_OWNERSHIP,visibility=GLAB_PROJECT_VISIBILITY,get_all=True)
    try:
        # processes = [Process(target=grab_data, args=(project,)) for project in projects]
        # # start all processes
        # for process in processes:
        #     process.start()
        # for process in processes:
        #     process.join()
        # print('All data sent to New Relic', flush=True)

        for project in projects:
            grab_data(project)
            # x = threading.Thread(target=grab_data, args=(project,))
            # x.start()
            # x.join()
        print('Exporter finished running, closing.')
    except Exception as e:
        print(e)

if __name__ == "__main__":
    # Initialize variables
    var.init()  
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
    