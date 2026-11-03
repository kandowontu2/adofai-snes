"""Keep loss-only visual effects out of the compiled successful-play route."""
SUCCESS=('perfectTag','earlyPerfectTag','latePerfectTag','veryEarlyTag','veryLateTag','hitTag','barelyTag')
FAILURE=('tooEarlyTag','tooLateTag','missTag','lossTag','onCheckpointTag')

def gameplay_actions(data):
    actions=[a for a in data.get('track_actions',[]) if a.get('active',True) and not a.get('minVfxOnly',False)]
    conditions={a['floor']:a for a in actions if a['eventType']=='SetConditionalEvents'}
    def allowed(a):
        tag=a.get('eventTag','');condition=conditions.get(a['floor'],{})
        if not tag or tag.upper()=='NONE':return True
        if any(condition.get(k)==tag for k in SUCCESS):return True
        return not any(condition.get(k)==tag for k in FAILURE)
    return [a for a in actions if allowed(a)]
