from __future__ import annotations
from abc import abstractmethod
from pathlib import Path

from App.App import Object, App, AudioWrapper
from App.lib import Lib
from App.Conf import Conf
import pygame as pg
from pygame import (
    KEYDOWN,
    KEYUP,
    Rect,
    font,
    mixer,
    time,
    display,
    event,
    key,
    image,
    mouse,
    Surface,
    sprite,
    transform,
)
from typing import (
    Any,
    Never,
)

import threading
from queue import Queue


class Game:
    """
    Container for ingame behaviour
    """

    miss = event.custom_type()
    good = event.custom_type()
    great = event.custom_type()
    perfect = event.custom_type()
    plusperfect = event.custom_type()

    START_TIME: int
    PASSED_TIME: int

    STATIC = sprite.Group()
    # Everything non rhythm game related that's still loaded
    LOADED = sprite.Group()
    # All note sprites are first loaded into this group
    ACTIVE = sprite.Group()
    # Notes that should be visible are then moved into this group
    PASSED = sprite.Group()
    # Notes should be moved here once hit and should then stop being updated and rendered

    @staticmethod
    def ingame_loop(level: Level_FILE, auto: bool) -> bool:
        """
        Instantiates own clock.
        Provides multiple return states:
        False - pass.
        True - fail OR quit: skip results screen and play fail graphic if fail.
        """

        QUIT = False
        KEY_QUEUE = Queue()

        def get_key_events():
            while True:
                for event in pg.event.get([pg.KEYDOWN, pg.KEYUP]):
                    timestamp = Game.PASSED_TIME
                    key_time = {"key": event, "time": timestamp}
                    KEY_QUEUE.put(key_time)
                    time.delay(1)

        key_thread = threading.Thread(target=get_key_events)
        key_thread.daemon = True
        key_thread.start()

        def failscreen() -> None:
            """Display the fail graphic upon failure."""
            pass

        health = 1000
        CLOCK = App.CLOCK
        SONG = Game.get_audio(level)
        LEVEL_LOADED = Game.load_level(level)

        for note in LEVEL_LOADED.notes:
            Game.LOADED.add(note)

        Game.START_TIME = App.DELTA_TIME()  # Call right before loop for accuracy
        Game.PASSED_TIME = Game.START_TIME

        AudioWrapper.play(SONG, AudioWrapper.song)
        INGAME = True

        # Dictionary to store key event lists for each key
        key_events_this_frame: dict[str, list[dict]] = {
            "s": [],
            "d": [],
            "f": [],
            " ": [],
            "j": [],
            "k": [],
            "l": [],
        }

        # Dictionary to track currently held keys for long notes
        held_keys = {}

        while INGAME:
            Game.PASSED_TIME = App.DELTA_TIME() - Game.START_TIME

            # Move notes from LOADED to ACTIVE based on time
            for sp in Game.LOADED:
                if sp.time <= Game.PASSED_TIME - 2000:
                    sp.remove(Game.LOADED)
                    sp.add(Game.ACTIVE)

            # Reset key events per frame
            for key in key_events_this_frame:
                key_events_this_frame[key].clear()

            # Process input events
            while not KEY_QUEUE.empty():
                event_data = KEY_QUEUE.get()
                pressed = event_data["key"]
                timestamp = event_data["time"]

                # Store multiple keydown and keyup events for each key
                key_name = pg.key.name(pressed.key)
                if key_name in key_events_this_frame:
                    key_events_this_frame[key_name].append(
                        {"event": pressed.type, "time": timestamp}
                    )

            # Process active notes based on key events
            if not auto:
                notes_hit_this_frame = set()

                # Iterate over each key event that occurred this frame
                for key, events in key_events_this_frame.items():
                    for event in events:
                        if event["event"] == pg.KEYDOWN:
                            # Process each note in the active notes list
                            for note in Game.ACTIVE:
                                if note in notes_hit_this_frame:
                                    continue  # Skip notes that were already hit in this frame

                                # Check if the note matches the key and is within the hit window
                                hit_window = abs(Game.PASSED_TIME - note.time)
                                if (
                                    note.required_key == key
                                    and hit_window <= Conf.HIT_WINDOWS["miss"]
                                ):
                                    if note.is_long_note:
                                        # Long note: store it as held
                                        held_keys[key] = {
                                            "note": note,
                                            "start_time": Game.PASSED_TIME,
                                        }
                                    else:
                                        # Short note: Check timing window and post appropriate event
                                        if hit_window <= Conf.HIT_WINDOWS["perfect"]:
                                            pg.event.post(
                                                pg.event.Event(Game.plusperfect)
                                            )
                                        elif hit_window <= Conf.HIT_WINDOWS["perfect"]:
                                            pg.event.post(pg.event.Event(Game.perfect))
                                        elif hit_window <= Conf.HIT_WINDOWS["great"]:
                                            pg.event.post(pg.event.Event(Game.great))
                                        elif hit_window <= Conf.HIT_WINDOWS["good"]:
                                            pg.event.post(pg.event.Event(Game.good))
                                        else:
                                            pg.event.post(pg.event.Event(Game.miss))

                                        note.remove(Game.ACTIVE)
                                        note.add(Game.PASSED)
                                        notes_hit_this_frame.add(note)
                                        break

                        elif event["event"] == pg.KEYUP:
                            # Handle key release for long notes
                            if key in held_keys:
                                held_note_info = held_keys[key]
                                note = held_note_info["note"]

                                # Check if key is released within the long note's release window
                                hit_window = abs(Game.PASSED_TIME - note.end_time)
                                if hit_window <= Conf.HIT_WINDOWS["miss"]:
                                    if hit_window <= Conf.HIT_WINDOWS["plusperfect"]:
                                        pg.event.post(
                                            pg.event.Event(Game.plusperfect)
                                        )  # Successful long note release
                                    elif hit_window <= Conf.HIT_WINDOWS["perfect"]:
                                        pg.event.post(pg.event.Event(Game.perfect))
                                    elif hit_window <= Conf.HIT_WINDOWS["great"]:
                                        pg.event.post(pg.event.Event(Game.great))
                                    elif hit_window <= Conf.HIT_WINDOWS["good"]:
                                        pg.event.post(pg.event.Event(Game.good))
                                    else:
                                        pg.event.post(pg.event.Event(Game.miss))

                                    note.remove(Game.ACTIVE)
                                    note.add(Game.PASSED)
                                else:
                                    # Penalize for releasing too early or too late
                                    pg.event.post(pg.event.Event(Game.miss))
                                    note.remove(Game.ACTIVE)
                                    note.add(Game.PASSED)

                                # Remove the key from held_keys once it's released
                                del held_keys[key]

                # Handle notes that weren't hit and are now too late
                for note in Game.ACTIVE:
                    if note.time <= Game.PASSED_TIME - Conf.HIT_WINDOWS["miss"]:
                        note.remove(Game.ACTIVE)
                        note.add(Game.PASSED)
                        pg.event.post(pg.event.Event(Game.miss))

            else:  # Auto-play logic
                for note in Game.ACTIVE:
                    if note.time <= Game.PASSED_TIME - 10:
                        note.remove(Game.ACTIVE)
                        note.add(Game.PASSED)
                        pg.event.post(pg.event.Event(Game.plusperfect))

            Game.ACTIVE.update()
            CLOCK.tick_busy_loop(120)

            if health <= 0:
                failscreen()
                break
            elif QUIT:
                break
            elif len(Game.ACTIVE) == 0:
                INGAME = False

        else:
            return False
        return True

    @staticmethod
    def load_level(level: Level_FILE) -> Level_MEMORY:
        return Level_MEMORY(level)

    @staticmethod
    def get_audio(level: Level_FILE) -> mixer.Sound:
        """
        For fetching the level audio for a level
        """

        info = level.info
        if "AudioFilename" in info.keys():
            SONG = mixer.Sound(
                Path(
                    Lib.PROJECT_ROOT,
                    "Assets",
                    "Levels",
                    str(level.meta["TitleUnicode"]),
                    level.info["AudioFilename"],
                )
            )
            return SONG
        else:
            App.quit_app(
                FileNotFoundError(
                    "Audio file not found in level metadata:",
                    level.meta["TitleUnicode"],
                )
            )


class Note(Object):
    """
    Strictly only a parent class to contain TapNote and LongNote as well as common logic

    TODO: Optimise runtime overhead of loading stuff
    """

    @property
    @abstractmethod
    def time(self) -> int:
        pass

    @property
    @abstractmethod
    def lane(self) -> int:
        pass

    @property
    @abstractmethod
    def state(self) -> sprite.Group:
        """
        Handles whether objects are still updated
        hits and misses are handled immediately before notes are passed here
        """
        pass

    @property
    def required_key(self) -> str:
        table = {
            0: "s",
            1: "d",
            2: "f",
            3: " ",
            4: "j",
            5: "k",
            6: "l",
        }
        return table[self.lane - 1]

    _white_tex = None
    _blue_tex = None

    @property
    def image(self) -> Surface:
        if Note._white_tex is None:
            Note._white_tex = image.load(Conf.NOTE_TEX_WHITE)
            Note._white_tex = transform.scale(Note._white_tex, (200, 100))

        if Note._blue_tex is None:
            Note._blue_tex = image.load(Conf.NOTE_TEX_BLUE)
            Note._blue_tex = transform.scale(Note._blue_tex, (200, 100))

        return Note._white_tex if self.lane in [0, 2, 4, 6] else Note._blue_tex

    def calc_pos(self) -> int:
        out = (self.time - Game.PASSED_TIME) * Conf.MULTIPLIER + Conf.CONSTANT
        return int(out)


class TapNote(Note):
    """
    tapnote logic
    """

    def __init__(self, lane: int, note_time: int) -> None:
        sprite.Sprite.__init__(self)
        self._lane = lane
        self._time = note_time

    def update(self) -> None:
        App.SCREEN.blit(self.image, self.position)

    @property
    def position(self) -> tuple[int, int]:
        return (self.lane, self.calc_pos())

    @property
    def time(self) -> int:
        return self._time

    @property
    def lane(self) -> int:
        return self._lane

    @property
    def rect(self) -> Rect:
        return self.image.get_rect()

    @property
    def state(self) -> sprite.Group:
        return self._state

    @state.setter
    def state(self, value: sprite.Group) -> None:
        self._state = value
        self.add(value)


class LongNote(Note):
    """
    LN logic
    """

    def __init__(self, lane: int, note_time: int, note_endtime: int) -> None:
        sprite.Sprite.__init__(self)
        self._lane = lane
        self._time = note_time
        self._endtime = note_endtime

    def update(self) -> None:
        App.SCREEN.blit(self.image, self.position)
        App.SCREEN.blit(self.image_body, self.position)

    @property
    def position(self) -> tuple[int, int]:
        return (Note.calc_pos(self), self.lane)

    @property
    def time(self) -> int:
        return self._time

    @property
    def endtime(self) -> int:
        return self._endtime

    @property
    def lane(self) -> int:
        return self._lane

    @property
    def rect(self) -> Rect:
        return self.image.get_rect()

    @property
    def state(self) -> sprite.Group:
        return self._state

    @state.setter
    def state(self, value: sprite.Group) -> None:
        self._state = value
        self.add(value)

    @property
    def image_body(self) -> Surface:
        tex = image.load(Conf.NOTE_TEX_BODY)
        tex = transform.scale(tex, ((self.endtime - self.time) / 50, 100))
        return tex

    @property
    def rect_body(self) -> Rect:
        return self.image_body.get_rect()

    """
    Hold tail textures MAY be implemented for certain skins and textures
    But will not be implemented with this version as most players prefer to have them invisible

    These are commented out but are perfectly valid implementations otherwise
    """
    # @property
    # def image_tail(self) -> Surface:
    #     tex = image.load(Conf.NOTE_TEX_TAIL)
    #     tex = transform.scale(tex, (200, 100))
    #     return tex

    # @property
    # def rect_tail(self) -> Rect:
    #     return self.image_tail.get_rect()


class Level_MEMORY:
    """
    The actual object passed to the level engine at runtime
    Ensures reasonable overheads and isolates level data from loaded sprites which are more expensive
    """

    @staticmethod
    def load_notes(line: list[str]) -> Note:
        note: TapNote | LongNote
        obj_type = None
        time = int(line[2])
        endtime = time
        lane = int(line[0])

        if int(line[3]) == 0:
            obj_type = TapNote
        elif int(line[3]) == 7:
            obj_type = LongNote
            endtime = int(line[5])

        if obj_type == TapNote:
            return TapNote(lane, time)
        elif obj_type == LongNote:
            return LongNote(lane, time, endtime)

        else:
            App.quit_app(FileNotFoundError("Loaded level file is of incorrect format."))

    def __init__(self, level: Level_FILE) -> None:
        """
        reads level data and removes invalid notes
        """

        self.notes: list[Note] = [Level_MEMORY.load_notes(line) for line in level.notes]
        self.meta = level.meta
        self.info = level.info


class Level_FILE:
    @staticmethod
    def parse_meta(path: Path) -> dict[str, Any]:
        """
        Horrific type safety but gets the job done

        Reads the .osu file and returns a dictionary containing the level data in several nested dictionaries and lists
        """

        General: dict[str, str] = dict()
        Metadata: dict[str, str | list[str]] = dict()
        Difficulty: dict[str, str] = dict()
        TimingPoints: list[list[str]] = list()
        HitObjects: list[list[str]] = list()

        out = {
            "G": General,
            "M": Metadata,
            "D": Difficulty,
            "T": TimingPoints,
            "H": HitObjects,
        }

        with path.open() as level:
            meta = level.readlines()
            section = ""
            for line in meta:
                match line:
                    case line if "[General]" in line:
                        section = "General"
                        continue

                    case line if "[Metadata]" in line:
                        section = "Metadata"
                        continue

                    case line if "[Difficulty]" in line:
                        section = "Difficulty"
                        continue

                    case line if "[TimingPoints]" in line:
                        section = "TimingPoints"
                        continue

                    case line if "[HitObjects]" in line:
                        section = "HitObjects"
                        continue

                    case line if "[Editor]" in line:
                        section = "Editor"
                        continue

                    case line if "[Events]" in line:
                        section = "Events"
                        continue

                    case _:
                        if line:
                            pass
                        else:
                            section = ""
                            continue

                if section == "Editor" or section == "Events":
                    continue

                elif section == "General":
                    pair = line.replace(" ", "").split(":")
                    General[pair[0]] = pair[1]

                elif section == "Metadata":
                    pair = line.split(":")
                    if pair[0] == "Tags":
                        Metadata[pair[0]] = pair[1].split(" ")
                        continue
                    Metadata[pair[0]] = pair[1]

                elif section == "Difficulty":
                    pair = line.split(":")
                    Difficulty[pair[0]] = pair[1]

                elif section == "TimingPoints":
                    point = line.split(",")
                    TimingPoints.append(point)

                elif section == "HitObjects":
                    obj = line.split(",")
                    HitObjects.append(obj)

                else:
                    pass

        return out

    def __init__(self, path: Path) -> None:
        self.data = Level_FILE.parse_meta(path)
        self.notes: list[list[str]] = self.data["H"]
        self.tpoints: list[list[str]] = self.data["T"]
        self.meta: dict[str, str | list[str]] = self.data["M"]
        self.info: dict[str, str] = self.data["G"]
        self.diff: dict[str, str] = self.data["D"]
