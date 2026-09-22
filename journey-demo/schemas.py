"""Strict API schemas: an empty JSON object is never a successful pipeline result."""
def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def array(item, minimum=0, maximum=200):
    return {'type': 'array', 'items': item, 'minItems': minimum, 'maxItems': maximum}


text = {'type': 'string', 'minLength': 1}
number = {'type': 'number'}
vector = array(number, 3, 3)
interval = array(number, 2, 2)
strings = array(text)

OBSERVATIONS = obj({
    'summary': text,
    'timeline': array(obj({'start_s': number, 'end_s': number, 'place': text,
        'activity': text, 'visual_evidence': text, 'people_visible': {'type': 'boolean'},
        'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']}}), 3, 30),
    'selected_stops': array(obj({'id': text, 'label': text, 'start_s': number,
        'end_s': number, 'terrain': text, 'structures': strings, 'palette': strings,
        'visible_travelers': strings, 'activities': strings,
        'evidence_timestamps_s': array(number, 1, 20), 'uncertainty': strings}), 2, 3),
    'limitations': strings,
})

WORLD = obj({
    'title': {'type': 'string', 'enum': ['My Travel Journey']},
    'units': {'type': 'string', 'enum': ['meters']},
    'up_axis': {'type': 'string', 'enum': ['Y']},
    'design_summary': text,
    'approximation_notes': array(text, 1, 20),
    'stops': array(obj({'id': text, 'label': text, 'caption': text,
        'source_range_s': interval, 'position': vector,
        'parts': array(obj({'id': text,
            'shape': {'type': 'string', 'enum': ['box', 'sphere', 'cylinder', 'cone']},
            'position': vector, 'scale': vector, 'rotation_deg': vector,
            'color': {'type': 'string', 'pattern': '^#[0-9a-fA-F]{6}$'},
            'role': text}), 20, 45)}), 2, 3),
})
