from pet_engine import PetEngine


def test_initial_state():
    state = PetEngine().snapshot()
    assert state['pet'] == {'name': 'Byte', 'mood': 'happy', 'health': 85, 'energy': 80, 'stress': 15, 'level': 1, 'xp': 0, 'total_xp': 0}
    assert state['events_seen'] == 0


def test_crash_and_recovery():
    engine = PetEngine()
    engine.apply({'id': 'a', 'ts': 'now', 'type': 'APP_CRASH', 'message': 'app died'})
    assert (engine.health, engine.energy, engine.stress, engine.mood) == (60, 68, 45, 'sick')
    engine.apply({'id': 'b', 'ts': 'now', 'type': 'BUILD_SUCCESS', 'message': 'fixed'})
    assert (engine.health, engine.energy, engine.stress, engine.total_xp, engine.mood) == (72, 78, 33, 30, 'excited')
    assert engine.alerts_seen == 1


def test_xp_level_and_limits():
    engine = PetEngine()
    for i in range(6):
        engine.apply({'type': 'BUILD_SUCCESS', 'message': str(i)})
    assert engine.snapshot()['pet']['level'] == 2
    assert engine.snapshot()['pet']['xp'] == 80
    assert engine.health == 100
    for i in range(100):
        engine.apply({'type': 'APP_CRASH', 'message': 'fail'})
    assert engine.health == 0 and engine.energy == 0 and engine.stress == 100


def test_metrics_are_not_game_events():
    engine = PetEngine()
    engine.apply({'type': 'METRIC', 'cpu': 36.4, 'ram': 42})
    engine.apply({'type': 'METRIC', 'cpu': -5, 'ram': 150})
    engine.apply({'type': 'METRIC', 'cpu': 'bad', 'ram': 4})
    assert engine.cpu == 36.4
    assert engine.ram == 42.0
    assert len(engine.metrics_history) == 1
    assert engine.events_seen == 0


def test_unknown_event_displayed_but_does_not_hurt_pet():
    engine = PetEngine()
    engine.apply({'type':'CUSTOM', 'message':'hello'})
    assert engine.events_seen == 1 and engine.health == 85


def test_recent_limit():
    engine = PetEngine()
    for index in range(100):
        engine.apply({'type':'CUSTOM', 'message':str(index), 'id':str(index)})
    assert len(engine.recent) == 40
    assert engine.recent[0]['id'] == '99'
