import schedule
import time
from get_resources import grab_data,get_runners
from global_variables import *
import concurrent.futures


        
def send_to_nr():
    projects = gl.projects.list(owned=GLAB_PROJECT_OWNERSHIP,visibility=GLAB_PROJECT_VISIBILITY,get_all=True)
    print("Found total of " + str(len(projects)) + " projects using -> OWNED: " + str(GLAB_PROJECT_OWNERSHIP) + " and VISIBILITY: " + str(GLAB_PROJECT_VISIBILITY) + ". \nChecking which ones match provided paths and project regex configuration")  
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(grab_data,projects)
    
    get_runners()
    time.sleep(1)
    if len(projects) == 0:
        print("Nothing to export check your configuration!!!")
    else:
        print('Exporter finished!!!')
    gl.session.close()
    
if GLAB_STANDALONE:
    # Run once, then schedule every GLAB_EXPORT_LAST_MINUTES
    send_to_nr()
    time.sleep(1)
    schedule.every(int(GLAB_EXPORT_LAST_MINUTES)).minutes.do(send_to_nr) 
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
    