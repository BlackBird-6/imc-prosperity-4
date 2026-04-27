
from datamodel import TradingState
class Trader:
    def run(self, state: TradingState):
        if state.timestamp % 100000 == 0:
            print(f'Timestamp: {state.timestamp}')
        return {}, 0, ''
