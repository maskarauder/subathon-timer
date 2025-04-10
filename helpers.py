#!/usr/bin/env python3

# Ugly, sorry.
# Fix if you want to.
def fuzzy_strtime_to_int(input: str) -> int:
    try:
        return int(input)
    except ValueError:
        nparam = input.count(':')

        negate = False
        if input.startswith('-'):
            negate = True
            input = input.lstrip('-')

        t = 0
        if nparam == 1 or nparam == 2:
            time_vals = input.split(':')
            time_vals.reverse()

            seconds = 0
            try:
                seconds += int(time_vals[0])
                if nparam >= 1:
                    seconds += int(time_vals[1]) * 60
                if nparam >= 2:
                    seconds += int(time_vals[2]) * 60 * 60

                t = seconds
            except ValueError:
                pass
        
            if t != 0:
                return t if not negate else t*-1
        
        #TODO: Maybe add support for stuff like "60m"?
        return 0

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