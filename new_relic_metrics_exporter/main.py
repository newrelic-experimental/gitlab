import schedule
import time
from get_resources import grab_data, get_runners
from shared.global_variables import *
import asyncio
import datetime

# Start timer
start_time = time.time()


def send_to_nr(project):
    asyncio.run(grab_data(project))


def run():
    projects = []
    for visibility in GLAB_PROJECT_VISIBILITIES:
        projects.extend(
            gl.projects.list(
                owned=GLAB_PROJECT_OWNERSHIP, visibility=visibility, get_all=True
            )
        )
    print(
        "Found total of "
        + str(len(projects))
        + " projects using -> OWNED: "
        + str(GLAB_PROJECT_OWNERSHIP)
        + " and VISIBILITIES: "
        + str(GLAB_PROJECT_VISIBILITIES)
        + ". \nChecking which ones match provided paths and project regex configuration"
    )
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = [send_to_nr(project) for project in projects]

    try:
        return loop.run_until_complete(asyncio.wait(tasks))
    finally:
        loop.close()
        asyncio.set_event_loop(None)
        return "DONE"


if __name__ == "__main__":
    projects = []
    for visibility in GLAB_PROJECT_VISIBILITIES:
        projects.extend(
            gl.projects.list(
                owned=GLAB_PROJECT_OWNERSHIP, visibility=visibility, get_all=True
            )
        )
    if len(projects) == 0:
        print("Nothing to export check your configuration!!!")
    else:
        if GLAB_STANDALONE:
            print("Running on standalone mode")
            # Run once, then schedule every GLAB_EXPORT_LAST_MINUTES
            run()
            get_runners()
            gl.session.close()
            print(
                "Exporter finished in "
                + str(datetime.timedelta(seconds=(time.time() - start_time)))
                + " minutes"
            )
            time.sleep(1)
            schedule.every(int(GLAB_EXPORT_LAST_MINUTES)).minutes.do(run)
            while 1:
                n = schedule.idle_seconds()
                if n is None:
                    # no more jobs
                    break
                elif n > 0:
                    # sleep exactly the right amount of time
                    print("Next job run in " + str(round(int(n) / 60)) + " minutes")
                    time.sleep(n)
                schedule.run_pending()
        else:
            run()
            get_runners()
            gl.session.close()
            print(
                "Exporter finished in "
                + str(datetime.timedelta(seconds=(time.time() - start_time)))
                + " minutes"
            )
