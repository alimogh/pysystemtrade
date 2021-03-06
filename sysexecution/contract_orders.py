import datetime
from copy import copy

from sysexecution.order_stack import orderStackData
from sysexecution.base_orders import Order, tradeableObject, no_order_id, no_children, no_parent, MODIFICATION_STATUS_NO_MODIFICATION
from syscore.genutils import  none_to_object, object_to_none
from syscore.objects import failure, success, missing_order

class contractTradeableObject(tradeableObject):
    def __init__(self, strategy_name, instrument_code, contract_id):
        """

        :param strategy_name: str
        :param instrument_code: str
        :param contract_id: a single contract_id YYYYMM, or a list of contract IDS YYYYMM for a spread order
        """
        if type(contract_id) is str:
            contract_id = list([contract_id])

        dict_def = dict(strategy_name = strategy_name, instrument_code = instrument_code, contract_id=contract_id)
        self._set_definition(dict_def)

    @classmethod
    def from_key(instrumentTradeableObject, key):
        strategy_name, instrument_code, contract_id_str = key.split("/")
        contract_id_list  = contract_id_str.split("_")

        return instrumentTradeableObject(strategy_name, instrument_code, contract_id_list)

    @property
    def contract_id(self):
        return self._definition['contract_id']

    @property
    def contract_id_key(self):
        return "_".join(self.contract_id)

    @property
    def alt_contract_id_key(self):
        if len(self.contract_id_key)==6:
            return self.contract_id_key+"00"

        if len(self.contract_id_key)==8:
            return self.contract_id_key[:6]

    @property
    def strategy_name(self):
        return self._definition['strategy_name']

    @property
    def instrument_code(self):
        return self._definition['instrument_code']

    @property
    def key(self):
        return "/".join([self.strategy_name, self.instrument_code, self.contract_id_key])

    @property
    def alt_key(self):
        return "/".join([self.strategy_name, self.instrument_code, self.alt_contract_id_key])


class contractOrder(Order):

    def __init__(self, *args, fill=None,
                 locked=False, order_id=no_order_id,
                 modification_status = MODIFICATION_STATUS_NO_MODIFICATION,
                 modification_quantity = None, parent=no_parent,
                 children=no_children, active=True,
                 algo_to_use="", reference_price=None,
                 limit_price = None, filled_price = None,
                 fill_datetime = None,
                 generated_datetime = None,
                 manual_fill = False, manual_trade = False,
                 roll_order = False,
                 inter_spread_order = False,
                 calendar_spread_order = None,
                 reference_of_controlling_algo = None
                 ):

        """
        :param args: Eithier a single argument 'strategy/instrument/contract_id' str, or strategy, instrument, contract_id; followed by trade
        i.e. contractOrder(strategy, instrument, contractid, trade,  **kwargs) or 'strategy/instrument/contract_id', trade, type, **kwargs)

        Contract_id can eithier be a single str or a list of str for spread orders, all YYYYMM
        If expressed inside a longer string, seperate contract str by '_'

        i.e. contractOrder('a strategy', 'an instrument', '201003', 6,  **kwargs)
         same as contractOrder('a strategy/an instrument/201003', 6,  **kwargs)
        contractOrder('a strategy', 'an instrument', ['201003', '201406'], [6,-6],  **kwargs)
          same as contractOrder('a strategy/an instrument/201003_201406', [6,-6],  **kwargs)

        :param fill: fill done so far, list of int
        :param locked: if locked an order can't be modified, bool
        :param order_id: ID given to orders once in the stack, do not use when creating order
        :param modification_status: whether the order is being modified, str
        :param modification_quantity: The new quantity trade we want to do once modified, int
        :param parent: int, order ID of parent order in upward stack
        :param children: list of int, order IDs of child orders in downward stack
        :param active: bool, inactive orders have been filled or cancelled
        :param algo_to_use: str, full pathname of method to use to execute order.
        :param reference_of_controlling_algo: str, the key of the controlling algo. If None not currently controlled.
        :param limit_price: float, limit orders only
        :param reference_price: float, used to benchmark order (usually price from previous days close)
        :param filled_price: float, used for execution calculations and p&l
        :param fill_datetime: datetime used for p&l
        :param generated_datetime: datetime order generated
        :param manual_fill: bool, fill entered manually
        :param manual_trade: bool, trade entered manually
        :param roll_order: bool, part of a (or if a spread an entire) roll order. Passive rolls will be False
        :param calendar_spread_order: bool, a calendar spread (intra-market) order
        :param inter_spread_order: bool, part of an instrument order that is a spread across multiple markets
        """

        tradeable_object, trade = self._resolve_args(args)
        self._tradeable_object = tradeable_object

        if type(trade) is int or type(trade) is float:
            trade = [int(trade)]

        if fill is None:
            fill = [0]*len(trade)

        if len(trade)==1:
            calendar_spread_order = False
        else:
            calendar_spread_order = True

        if generated_datetime is None:
            generated_datetime = datetime.datetime.now()

        self._trade = trade
        self._fill = fill
        self._fill_datetime = fill_datetime
        self._filled_price = filled_price
        self._locked = locked
        self._order_id = order_id
        self._modification_status = modification_status
        self._modification_quantity = modification_quantity
        self._parent = parent
        self._children = children
        self._active = active
        self._order_info = dict(algo_to_use=algo_to_use, reference_price=reference_price,
                 limit_price = limit_price,
                                manual_trade = manual_trade, manual_fill = manual_fill,
                                roll_order = roll_order, calendar_spread_order = calendar_spread_order,
                                inter_spread_order = inter_spread_order, generated_datetime = generated_datetime,
                                reference_of_controlling_algo = reference_of_controlling_algo)

    def _resolve_args(self, args):
        if len(args)==2:
            tradeable_object = contractTradeableObject.from_key(args[0])
            trade = args[1]
        elif len(args)==4:
            strategy=args[0]
            instrument = args[1]
            contract_id = args[2]
            trade = args[3]
            tradeable_object = contractTradeableObject(strategy, instrument, contract_id)
        else:
            raise Exception("contractOrder(strategy, instrument, contractid, trade,  **kwargs) or ('strategy/instrument/contract_id', trade, **kwargs) ")

        return tradeable_object, trade

    def __repr__(self):
        my_repr = super().__repr__()
        if self.filled_price is not None and self.fill_datetime is not None:
            my_repr = my_repr + "Fill %.2f on %s" % (self.filled_price, self.fill_datetime)
        my_repr = my_repr+" %s" % str(self._order_info)

        return my_repr

    def terse_repr(self):
        order_repr = super().__repr__()
        return order_repr


    @classmethod
    def from_dict(instrumentOrder, order_as_dict):
        trade = order_as_dict.pop('trade')
        key = order_as_dict.pop('key')
        fill = order_as_dict.pop('fill')
        filled_price = order_as_dict.pop('filled_price')
        fill_datetime = order_as_dict.pop('fill_datetime')

        locked = order_as_dict.pop('locked')
        order_id = none_to_object(order_as_dict.pop('order_id'), no_order_id)
        modification_status = order_as_dict.pop('modification_status')
        modification_quantity = order_as_dict.pop('modification_quantity')
        parent = none_to_object(order_as_dict.pop('parent'), no_parent)
        children = none_to_object(order_as_dict.pop('children'), no_children)
        active = order_as_dict.pop('active')

        order_info = order_as_dict

        order = contractOrder(key, trade, fill=fill, locked = locked, order_id = order_id,
                      modification_status = modification_status,
                      modification_quantity = modification_quantity,
                      parent = parent, children = children,
                      active = active, fill_datetime = fill_datetime, filled_price = filled_price,
                      **order_info)

        return order

    @property
    def strategy_name(self):
        return self._tradeable_object.strategy_name

    @property
    def instrument_code(self):
        return self._tradeable_object.instrument_code

    @property
    def contract_id(self):
        return self._tradeable_object.contract_id

    @property
    def contract_id_key(self):
        return self._tradeable_object.contract_id_key

    @property
    def algo_to_use(self):
        return self._order_info['algo_to_use']

    @algo_to_use.setter
    def algo_to_use(self, algo_to_use):
        self._order_info['algo_to_use'] = algo_to_use

    @property
    def generated_datetime(self):
        return self._order_info['reference_datetime']

    @property
    def reference_price(self):
        return self._order_info['reference_price']

    @reference_price.setter
    def reference_price(self, reference_price):
        self._order_info['reference_price'] = reference_price

    @property
    def limit_price(self):
        return self._order_info['limit_price']

    @limit_price.setter
    def limit_price(self, limit_price):
        self._order_info['limit_price'] = limit_price

    @property
    def manual_trade(self):
        return self._order_info['manual_trade']

    @property
    def manual_fill(self):
        return self._order_info['manual_fill']

    @manual_fill.setter
    def manual_fill(self, manual_fill):
        self._order_info['manual_fill'] = manual_fill


    @property
    def roll_order(self):
        return self._order_info['roll_order']

    @property
    def calendar_spread_order(self):
        return self._order_info['calendar_spread_order']

    @property
    def reference_of_controlling_algo(self):
        return self._order_info['reference_of_controlling_algo']

    def is_order_controlled_by_algo(self):
        return self._order_info['reference_of_controlling_algo'] is not None

    def add_controlling_algo_ref(self, control_algo_ref):
        if self.is_order_controlled_by_algo():
            raise Exception("Already controlled by %s" % self.reference_of_controlling_algo)
        self._order_info['reference_of_controlling_algo'] = control_algo_ref

        return success

    def release_order_from_algo_control(self):
        self._order_info['reference_of_controlling_algo'] = None

    @property
    def inter_spread_order(self):
        return self._order_info['inter_spread_order']

    def fill_less_than_or_equal_to_desired_trade(self, proposed_fill

                                                 ):
        return all([x<=y for x,y in zip(proposed_fill, self.trade)])

    def fill_equals_zero(self):
        return all([x==0 for x in self.fill])

    def new_qty_less_than_fill(self, new_qty):
        return any([x<y for x,y in zip(new_qty, self.fill)])

    def fill_equals_desired_trade(self):
        return all([x==y for x,y in zip(self.trade, self.fill)])

    def is_zero_trade(self):
        return all([x==0 for x in self.trade])

    def same_trade_size(self, other):
        my_trade = self.trade
        other_trade = other.trade

        return all([x==y for x,y in zip(my_trade, other_trade)])

    def fill_equals_modification_quantity(self):
        if self.modification_quantity is None:
            return False
        else:
            return all([x==y for x,y in zip(self.modification_quantity, self.fill)])



class contractOrderStackData(orderStackData):
    def __repr__(self):
        return "Contract order stack: %s" % str(self._stack)

    def put_list_of_orders_on_stack(self, list_of_contract_orders, unlock_when_finished=True):
        """
        Put a list of new orders on the stack. We lock these before placing on.

        If any do not return order_id (so something has gone wrong) we remove all the relevant orders and return failure

        If all work out okay, we unlock the orders

        :param list_of_contract_orders:
        :return: list of order_ids or failure
        """
        if len(list_of_contract_orders)==0:
            return []
        log = self.log.setup(strategy_name = list_of_contract_orders[0].strategy_name,
                             instrument_code = list_of_contract_orders[0].instrument_code,
                             instrument_order_id = list_of_contract_orders[0].parent)

        list_of_child_ids = []
        status = success
        for contract_order in list_of_contract_orders:
            contract_order.lock_order()
            child_id = self.put_order_on_stack(contract_order)
            if type(child_id) is not int:
                log.warn("Failed to put contract order %s on stack error %s, rolling back entire transaction" %
                         (str(contract_order), str(child_id)),
                         contract_date = contract_order.contract_id_key)
                status = failure
                break

            else:
                list_of_child_ids.append(child_id)

        # At this point we eithier have total failure (list_of_child_ids is empty, status failure),
        #    or partial failure (list of child_ids is part filled, status failure)
        #    or total success

        if status is failure:
            # rollback the orders we added
            self.rollback_list_of_orders_on_stack(list_of_child_ids)
            return failure

        # success
        if unlock_when_finished:
            self.unlock_list_of_orders(list_of_child_ids)

        return list_of_child_ids

    def rollback_list_of_orders_on_stack(self, list_of_child_ids):
        self.log.warn("Rolling back addition of child orders %s" % str(list_of_child_ids))
        for order_id in list_of_child_ids:
            self._unlock_order_on_stack(order_id)
            self.deactivate_order(order_id)
            self.remove_order_with_id_from_stack(order_id)

        return success


    def unlock_list_of_orders(self, list_of_child_ids):
        for order_id in list_of_child_ids:
            self._unlock_order_on_stack(order_id)

        return success

    def manual_fill_for_order_id(self, order_id, fill_qty, filled_price=None, fill_datetime=None):
        result = self.change_fill_quantity_for_order(order_id, fill_qty, filled_price=filled_price,
                                            fill_datetime=fill_datetime)
        if result is failure:
            return failure

        # all good need to show it was a manual fill
        order = self.get_order_with_id_from_stack(order_id)
        order.manual_fill = True
        result = self._change_order_on_stack(order_id, order, check_if_orders_being_modified=False)

        return result

    def add_controlling_algo_ref(self, order_id, control_algo_ref):
        """

        :param order_id: int
        :param control_algo_ref: str or None
        :return:
        """
        if control_algo_ref is None:
            return self.release_order_from_algo_control(order_id)

        existing_order = self.get_order_with_id_from_stack(order_id)
        if existing_order is missing_order:
            raise Exception("Can't add controlling ago as order %d doesn't exist" % order_id)

        try:
            modified_order = copy(existing_order)
            modified_order.add_controlling_algo_ref(control_algo_ref)
        except Exception as e:
            raise Exception("%s couldn't add controlling algo %s to order %d" % (str(e), control_algo_ref, order_id))

        result = self._change_order_on_stack(order_id, modified_order, check_if_orders_being_modified=False)

        if result is not success:
            raise Exception("%s when trying to add controlling algo to order %d" % (str(result), order_id))

        return success

    def release_order_from_algo_control(self, order_id):
        existing_order = self.get_order_with_id_from_stack(order_id)
        if existing_order is missing_order:
            raise Exception("Can't release controlling ago as order %d doesn't exist" % order_id)

        if not existing_order.is_order_controlled_by_algo():
            # No change required
            return success

        try:
            modified_order = copy(existing_order)
            modified_order.release_order_from_algo_control()
        except Exception as e:
            raise Exception("%s couldn't release controlling algo for order %d" % (str(e), order_id))

        result = self._change_order_on_stack(order_id, modified_order, check_if_orders_being_modified=False)

        if result is not success:
            raise Exception("%s when trying to add controlling algo to order %d" % (str(result), order_id))

        return success


def log_attributes_from_contract_order(log, contract_order):
    """
    Returns a new log object with contract_order attributes added

    :param log: logger
    :param instrument_order:
    :return: log
    """
    new_log = log.setup(
              strategy_name=contract_order.strategy_name,
              instrument_code=contract_order.instrument_code,
              contract_order_id=object_to_none(contract_order.order_id, no_order_id),
              instrument_order_id = object_to_none(contract_order.parent, no_parent, 0))


    return new_log