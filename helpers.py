#!/usr/bin/env python3

# Ugly, sorry.
# Fix if you want to.
def fuzzy_strtime_to_int(value: str) -> int:
    original_value = value
    try:
        return int(value)
    except ValueError:
        negate = False
        if value.startswith('-'):
            negate = True
            value = value[1:]

        nparam = value.count(':')
        if nparam > 2:
            raise ValueError(f'Invalid time value: {original_value!r}')

        time_vals = value.split(':')
        time_vals.reverse()

        seconds = 0
        try:
            seconds += int(time_vals[0])
            if nparam >= 1:
                seconds += int(time_vals[1]) * 60
            if nparam >= 2:
                seconds += int(time_vals[2]) * 60 * 60
        except (IndexError, ValueError) as error:
            raise ValueError(f'Invalid time value: {original_value!r}') from error
    
        if negate:
            seconds *= -1
        
        return seconds

def int_to_strtime(input: int) -> str:
    if (input < 0):
        return 'DONE!'

    hours = str(int(input//3600))

    minutes = int((input%3600)//60)
    if minutes < 10:
        minutes = '0' + str(minutes)
    else:
        minutes = str(minutes)

    seconds = int((input%3600)%60)
    if seconds < 10:
        seconds = '0' + str(seconds)
    else:
        seconds = str(seconds)
        
    return f'{hours}:{minutes}:{seconds}'
