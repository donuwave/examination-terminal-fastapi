from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="UTC")


def start_scheduler():
    if scheduler.running:
        return

    # Импорт здесь, чтобы планировщик можно было подключать без загрузки всего приложения.
    from api_v1.notification.jobs import run_pause_over

    scheduler.add_job(
        run_pause_over,
        "interval",
        seconds=60,
        id="pause_over",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    print("Scheduler запущен!")
