"""Read-only Windows notifications, system health and opted-in project/process checks."""
import asyncio
import hashlib
from pathlib import Path
import subprocess
import time

import psutil


def event(source, key, title, body='', priority=0, created=None):
    return {'id': source + ':' + key, 'source': source, 'title': title, 'body': body,
            'priority': priority, 'created': created or time.time()}


class WindowsNotifications:
    name = 'Windows notifications'

    def collect(self):
        async def read():
            from winrt.windows.ui.notifications.management import UserNotificationListener, UserNotificationListenerAccessStatus
            from winrt.windows.ui.notifications import NotificationKinds
            listener = UserNotificationListener.current
            if listener.get_access_status() != UserNotificationListenerAccessStatus.ALLOWED:
                raise RuntimeError('Windows notification access is not allowed. Enable access in Windows settings.')
            items = await listener.get_notifications_async(NotificationKinds.TOAST)
            results = []
            for item in items:
                source = item.app_info.display_info.display_name or 'Windows app'
                # Avoid recursively reading our own spoken/printed updates as new messages.
                if source.lower() in {'zeno', 'chatgpt', 'codex'}:
                    continue
                binding = item.notification.visual.get_binding('ToastGeneric')
                if not binding:
                    continue
                texts = [part.text for part in binding.get_text_elements() if part.text]
                if not texts:
                    continue
                created = item.creation_time.timestamp()
                if created < time.time() - 86400:
                    continue
                key = hashlib.sha256(f'{item.id}:{created}:{texts}'.encode()).hexdigest()
                results.append(event(source, key, texts[0], ' '.join(texts[1:]), created=created))
            return results
        return asyncio.run(asyncio.wait_for(read(), timeout=15))


class WorkAndSystem:
    name = 'Work and system'

    def __init__(self, store, projects):
        self.store = store
        if store.get('projects') is None:
            store.set('projects', projects)
        self.cpu_samples = 0

    def collect(self):
        results = []
        battery = psutil.sensors_battery()
        low = bool(battery and battery.percent <= 20 and not battery.power_plugged)
        if low and not self.store.get('battery_low', False):
            results.append(event('System', str(time.time_ns()), f'Battery is at {int(battery.percent)}%. Please connect the charger.', priority=1))
        self.store.set('battery_low', low)
        self.cpu_samples = self.cpu_samples + 1 if psutil.cpu_percent() >= 90 else 0
        if self.cpu_samples == 3:
            results.append(event('System', str(time.time_ns()), 'CPU usage has stayed above 90% for several checks.'))
        memory_high = psutil.virtual_memory().percent >= 90
        if memory_high and not self.store.get('memory_high', False):
            results.append(event('System', str(time.time_ns()), 'Memory usage is above 90%.'))
        self.store.set('memory_high', memory_high)
        for folder in self.store.get('projects', []):
            path = Path(folder)
            if not (path / '.git').exists():
                continue
            result = subprocess.run(['git', '-C', str(path), 'status', '--porcelain=v1', '--branch'],
                                    capture_output=True, text=True, timeout=10,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                continue
            signature = hashlib.sha256(result.stdout.encode()).hexdigest()
            key = 'project:' + str(path)
            old = self.store.get(key)
            changed = len([line for line in result.stdout.splitlines() if not line.startswith('##')])
            summary = f'{path.name}: {changed} changed or untracked files.'
            if 'ahead ' in result.stdout.splitlines()[0]:
                summary += ' Local commits are waiting to be pushed.'
            self.store.set(key, {'signature': signature, 'summary': summary})
            if old and old['signature'] != signature:
                results.append(event('Projects', str(time.time_ns()), summary))
        watched = self.store.get('processes', [])
        remaining = []
        for item in watched:
            try:
                process = psutil.Process(item['pid'])
                running = process.is_running() and process.create_time() == item['started']
            except psutil.Error:
                running = False
            if running:
                remaining.append(item)
            else:
                results.append(event('Processes', f"{item['pid']}:{item['started']}",
                                     f"{item['name']} has stopped. Its exit result is unknown."))
        if remaining != watched:
            self.store.set('processes', remaining)
        reminders = self.store.get('reminders', [])
        for reminder in reminders:
            if reminder['due'] <= time.time() and not self.store.contains('Reminders:' + reminder['id']):
                results.append(event('Reminders', reminder['id'], reminder['text'], priority=1))
        # Retain until ingestion is confirmed, so a crash between collection and save cannot lose it.
        self.store.set('reminders', [r for r in reminders if not self.store.contains('Reminders:' + r['id'])])
        return results
