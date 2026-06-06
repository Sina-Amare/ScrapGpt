from app.core import scheduler as scheduler_module


def test_configure_scheduler_only_registers_watchdog_job():
    scheduler_module.scheduler.remove_all_jobs()

    scheduler_module.configure_scheduler()

    job_ids = {job.id for job in scheduler_module.scheduler.get_jobs()}
    assert job_ids == {"watchdog_cleanup"}
