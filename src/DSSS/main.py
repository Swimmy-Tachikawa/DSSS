
from __future__ import annotations

from datetime import datetime
from gdrivemgr import AuthInfo

from .process_test import StudentTimedUploader


def generate_times(time: tuple[int, int]) -> tuple[datetime, datetime]:
    now = datetime.now()
    start_time = now.replace(hour=time[0], minute=time[1], second=0, microsecond=0)
    end_time = now.replace(hour=time[0]+1+(time[1]+10)//60, minute=(time[1]+10)%60, second=0, microsecond=0)
    return start_time, end_time


TIMES = tuple([
    generate_times(time)
    for time in (
        (10, 00),
        (11, 10),
        (13, 30),
        (14, 40),
        (15, 50),
        (17, 00),
    )
])


def main(
        client_secrets="client_secrets.json",
        token_file="token.json"
):

    auth = AuthInfo(
        kind="oauth",
        data={
            "client_secrets_file": client_secrets,
            "token_file": token_file,
        },
    )

    uploader = StudentTimedUploader(
        auth=auth,
        root_folder_id="1FOdJBovjuaXJr1IDmRAJdR5ULQlOQUNs",
    )

    done = False
    while not done:
        for idx, (start_t, end_t) in enumerate(TIMES):
            print(f"{idx}: {start_t} ~ {end_t}")
            continue
        target_idx = input("共有する時間帯のidx値を入力: ")
        try:
            target_idx = int(target_idx)
            target_time = TIMES[target_idx]
        except ValueError as e:
            print("数値以外が入力されました")
        except IndexError as e:
            print("範囲外のidx値が入力されました")
        else:
            done = target_time in TIMES

    summary = uploader.upload_updated_files(
        local_directory="../../dsss_test",
        start_time=target_time[0],
        end_time=target_time[1],
    )

    print(summary.uploaded_count)
    for item in summary.selected_files:
        print(item.path.name, item.modified_time)
        continue

    return
