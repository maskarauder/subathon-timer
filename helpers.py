#!/usr/bin/env python3

# Ugly, sorry.
# Fix if you want to.
def fuzzy_strtime_to_int(input: str) -> int:
    try:
        return int(input)
    except ValueError:
        negate = False
        if input.startswith('-'):
            negate = True
            input = input.lstrip('-')

        nparam = input.count(':')
        if nparam > 2:
            return 0

        time_vals = input.split(':')
        time_vals.reverse()

        seconds = 0
        try:
            seconds += int(time_vals[0])
            if nparam >= 1:
                seconds += int(time_vals[1]) * 60
            if nparam >= 2:
                seconds += int(time_vals[2]) * 60 * 60
        except ValueError:
            return 0
    
        if negate:
            seconds *= -1
        
        return seconds

def int_to_strtime(input: int) -> str:
    if (input < 0):
        return 'DONE!'

    hours = str(input//3600)

    minutes = (input%3600)//60
    if minutes < 10:
        minutes = '0' + str(minutes)
    else:
        minutes = str(minutes)

    seconds = (input%3600)%60
    if seconds < 10:
        seconds = '0' + str(seconds)
    else:
        seconds = str(seconds)
        
    return f'{hours}:{minutes}:{seconds}'