import asyncio
from typing import Union
from xrpl.clients import JsonRpcClient
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.models import (XRP, AccountOffers, BookOffers,
                         IssuedCurrency, AccountInfo,
                         IssuedCurrencyAmount, OfferCancel,
                         OfferCreate, AccountLines, OfferCreate, OfferCreateFlag, Tx, GatewayBalances)
from xrpl.utils import drops_to_xrp, xrp_to_drops

from Misc import (memo_builder, validate_hex_to_symbol, is_hex, validate_hex_to_symbol)


# remind XRPL to announce us as part when we are done

def xm():
    return [memo_builder("Done-with-xamm.finance:", "https://xamm.finance")]

M_SOURCE_TAG = 1010101

def cancel_offer(sender_addr: str, offer_seq: int, fee: str = None) -> dict:
    """cancel an offer"""
    txn = OfferCancel(account=sender_addr, offer_sequence=offer_seq, fee=fee, memos=xm(), source_tag=M_SOURCE_TAG)
    return txn.to_xrpl()

def create_order_book_liquidity(sender_addr: str, buy: Union[float, IssuedCurrencyAmount], sell: Union[float, IssuedCurrencyAmount], expiry_date: int = None, fee: str = None) -> dict:
    """create an offer as passive; it doesn't immediately consume offers that match it, just stays on the ledger as an object for liquidity"""
    flags = [OfferCreateFlag.TF_PASSIVE]
    tx_dict = {}
    if isinstance(buy, float) and isinstance(sell, IssuedCurrencyAmount): # check if give == xrp and get == asset
        txn = OfferCreate(account=sender_addr, taker_pays=xrp_to_drops(buy), taker_gets=sell, flags=flags, expiration=expiry_date, fee=fee, memos=xm(), source_tag=M_SOURCE_TAG)
        tx_dict = txn.to_xrpl()
    if isinstance(buy, IssuedCurrencyAmount) and isinstance(sell, float): # check if give == asset and get == xrp
        txn = OfferCreate(account=sender_addr, taker_pays=buy, taker_gets=xrp_to_drops(sell), flags=flags, expiration=expiry_date, fee=fee, memos=xm(), source_tag=M_SOURCE_TAG)
        tx_dict = txn.to_xrpl()
    if isinstance(buy, IssuedCurrencyAmount) and isinstance(sell, IssuedCurrencyAmount): # check if give and get are == asset
        txn = OfferCreate(account=sender_addr, taker_pays=buy, taker_gets=sell, flags=flags, expiration=expiry_date, fee=fee, memos=xm(), source_tag=M_SOURCE_TAG)
        tx_dict = txn.to_xrpl()
    return tx_dict

def order_book_swap(sender_addr: str, buy: Union[float, IssuedCurrencyAmount], sell: Union[float, IssuedCurrencyAmount], tf_sell: bool = False, tf_fill_or_kill: bool = False, tf_immediate_or_cancel: bool = False, fee: str = None) -> dict:
    """create an offer that either matches with existing offers to get entire sell amount or cancels\n
    if swap_all is enabled, this will force exchange all the paying units regardless of profit or loss\n

    if tecKILLED is the result, exchange didnt go through because all of the `buy` couldnt be obtained. recommend enabling swap_all
    """
    flags = []
    if tf_sell:
        flags.append(OfferCreateFlag.TF_SELL)
    if tf_fill_or_kill:
        flags.append(OfferCreateFlag.TF_FILL_OR_KILL)
    if tf_immediate_or_cancel:
        flags.append(OfferCreateFlag.TF_IMMEDIATE_OR_CANCEL)
    tx_dict = {}
    if isinstance(buy, float) and isinstance(sell, IssuedCurrencyAmount): # check if give == xrp and get == asset
        txn = OfferCreate(account=sender_addr, taker_pays=xrp_to_drops(buy), taker_gets=sell, flags=flags, fee=fee, memos=xm(), source_tag=M_SOURCE_TAG)
        tx_dict = txn.to_xrpl()
    if isinstance(buy, IssuedCurrencyAmount) and isinstance(sell, float): # check if give == asset and get == xrp
        txn = OfferCreate(account=sender_addr, taker_pays=buy, taker_gets=xrp_to_drops(sell), flags=flags, fee=fee, memos=xm(), source_tag=M_SOURCE_TAG)
        tx_dict = txn.to_xrpl()
    if isinstance(buy, IssuedCurrencyAmount) and isinstance(sell, IssuedCurrencyAmount): # check if give and get are == asset
        txn = OfferCreate(account=sender_addr, taker_pays=buy, taker_gets=sell, flags=flags, fee=fee, memos=xm(), source_tag=M_SOURCE_TAG)
        tx_dict = txn.to_xrpl()
    return tx_dict


class XAMM(AsyncJsonRpcClient):
    def __init__(self, url: str) -> None:
        self.client = AsyncJsonRpcClient(url)

    async def get_account_order_book_liquidity(self, wallet_addr: str) -> list:
        """return all offers that are liquidity an account created"""
        offer_list = []

        req = AccountOffers(account=wallet_addr, ledger_index="validated")
        response = await self.client.request(req)
        result = response.result
        if "offers" in result:
            offers = result["offers"]
            for offer in offers:
                if 0x00010000 & offer["flags"] == 0x00010000:
                    of = {}
                    of["flags"] = offer["flags"]
                    of["sequence"] = offer["seq"]
                    of["quality"] = offer["quality"]# str(drops_to_xrp(offer["quality"])) # rate is subject to error from the blockchain because xrp returned in this call has no decimal  # The exchange rate of the offer, as the ratio of the original taker_pays divided by the original taker_gets. rate = pay/get
                    if isinstance(offer["taker_pays"], dict):
                        of["buy_token"] = validate_hex_to_symbol(offer["taker_pays"]["currency"])
                        of["buy_issuer"] = offer["taker_pays"]["issuer"]
                        of["buy_amount"] = offer["taker_pays"]["value"]
                    elif isinstance(offer["taker_pays"], str):
                        of["buy_token"] = "XRP"
                        of["buy_issuer"] = ""
                        of["buy_amount"] = str(drops_to_xrp(offer["taker_pays"]))
                    if isinstance(offer["taker_gets"], dict):
                        of["sell_token"] = validate_hex_to_symbol(offer["taker_gets"]["currency"])
                        of["sell_issuer"] = offer["taker_gets"]["issuer"]
                        of["sell_amount"] = offer["taker_gets"]["value"]
                    elif isinstance(offer["taker_gets"], str):
                        of["sell_token"] = "XRP"
                        of["sell_issuer"] = ""
                        of["sell_amount"] = str(drops_to_xrp(offer["taker_gets"]))
                    of["rate"] = float(of["sell_amount"])/float(of["buy_amount"])
                    offer_list.append(of)
        return offer_list

    async def token_balance(self, wallet_addr: str, name: str, issuer: str) -> list:
        info = {"token": name, "issuer": issuer, "amount": None, "limit": None, "no_ripple": None, "freeze_status": None}
        acc_info = AccountLines(account=wallet_addr, ledger_index="")
        response = await self.client.request(acc_info)
        result = response.result
        if "lines" in result:
            lines = result["lines"]
            for line in lines:
                if isinstance(is_hex(line["currency"]), Exception):
                    pass
                elif validate_hex_to_symbol(line["currency"]) == validate_hex_to_symbol(name) and line["account"] == issuer:
                    info["token"] = validate_hex_to_symbol(line["currency"])
                    info["issuer"] = line["account"]
                    info["amount"] = line["balance"]
                    info["limit"] = line["limit"]
                    info["no_ripple"] = line["no_ripple"] if "no_ripple" in line else ""
                    info["freeze_status"] = line["freeze"] if "freeze" in line else ""
        return info

    async def status(self, txid: str) -> dict:
        response = "Failed"
        query = Tx(transaction=txid)
        
        response = await self.client.request(query)
        result = response.result
        if "Account" in result:
            response = "Success" if result["meta"]["TransactionResult"] == "tesSUCCESS" else "Failed"
        return response

    async def token_exists(self, token: str, issuer: str) -> dict:
        response = {"token": token, "issuer": issuer, "exists": False}
        
        response = await self.client.request(GatewayBalances(account=issuer, ledger_index="validated"))
        result = response.result
        if "obligations" in result:
            obligations = result["obligations"]
            for key, value in obligations.items():
                if validate_hex_to_symbol(key) == validate_hex_to_symbol(token):
                    response["token"] = validate_hex_to_symbol(key)
                    response["issuer"] = issuer
                    response["exists"] = True
        return response

    async def xrp_balance(self, wallet_addr: str) -> str:
        """return xrp balance and objects count"""
        balance = 0
        owner_count = 0
        spend_balance = 0
        
        acc_info = AccountInfo(account=wallet_addr, ledger_index="validated")
        response = await self.client.request(acc_info)
        result = response.result
        if "account_data" in result:
            balance = int(result["account_data"]["Balance"]) - 10000000
            owner_count = int(result["account_data"]["OwnerCount"])
            spend_balance =  str(drops_to_xrp(str(balance - (2000000 * owner_count))))
        return spend_balance 

    async def pending_offers(self, wallet_addr: str) -> list:
        offer_list = []
        
        req = AccountOffers(account=wallet_addr, ledger_index="validated")
        response = await self.client.request(req)
        result = response.result
        if "offers" in result:
            offers = result["offers"]
            for offer in offers:
                of = {}
                of["flags"] = offer["flags"]
                of["sequence"] = offer["seq"]
                of["quality"] = offer["quality"]# str(drops_to_xrp(offer["quality"])) # rate is subject to error from the blockchain because xrp returned in this call has no decimal  # The exchange rate of the offer, as the ratio of the original taker_pays divided by the original taker_gets. rate = pay/get
                if isinstance(offer["taker_pays"], dict):
                    of["buy_token"] = validate_hex_to_symbol(offer["taker_pays"]["currency"])
                    of["buy_issuer"] = offer["taker_pays"]["issuer"]
                    of["buy_amount"] = offer["taker_pays"]["value"]
                elif isinstance(offer["taker_pays"], str):
                    of["buy_token"] = "XRP"
                    of["buy_issuer"] = ""
                    of["buy_amount"] = str(drops_to_xrp(offer["taker_pays"]))

                if isinstance(offer["taker_gets"], dict):
                    of["sell_token"] = validate_hex_to_symbol(offer["taker_gets"]["currency"])
                    of["sell_issuer"] = offer["taker_gets"]["issuer"]
                    of["sell_amount"] = offer["taker_gets"]["value"]
                elif isinstance(offer["taker_gets"], str):
                    of["sell_token"] = "XRP"
                    of["sell_issuer"] = ""
                    of["sell_amount"] = str(drops_to_xrp(offer["taker_gets"]))
                of["rate"] = float(of["sell_amount"])/float(of["buy_amount"])
                offer_list.append(of)
        return offer_list


    async def sort_best_offer(self, buy: Union[XRP, IssuedCurrency], sell: Union[XRP, IssuedCurrency], best_buy: bool = False, best_sell: bool = False, mainnet: bool = False) -> dict:
        """return all available orders and best {option} first, choose either best_buy or best_sell"""
        best = {}

        if best_sell:
            req = BookOffers(taker_gets=sell, taker_pays=buy, ledger_index="validated")
            response = await self.client.request(req)
            result = response.result
            if "offers" in result:
                offers: list = result["offers"]
                # sort offer list and retur n highest rate first
                offers.sort(key=lambda object: object["quality"], reverse=True)
                index = 0
                for offer in offers:
                    of = {}
                    of["creator"] = offer["Account"]
                    of["offer_id"] = offer["index"]
                    of["flags"] = offer["Flags"]
                    of["sequence"] = offer["Sequence"] # offer id
                    of["rate"] = offer["quality"]
                    of["creator_liquidity"] = ""
                    if "owner_funds" in offer:
                        of["creator_liquidity"] = offer["owner_funds"] # available amount the offer creator of `sell_token` is currently holding
                    if isinstance(offer["TakerPays"], dict):
                        of["buy_token"] = validate_hex_to_symbol(offer["TakerPays"]["currency"])
                        of["buy_issuer"] = offer["TakerPays"]["issuer"]
                        of["buy_amount"] = offer["TakerPays"]["value"]
                    elif isinstance(offer["TakerPays"], str):
                        of["buy_token"] = "XRP"
                        of["buy_issuer"] = ""
                        of["buy_amount"] = str(drops_to_xrp(offer["TakerPays"]))

                    if isinstance(offer["TakerGets"], dict):
                        of["sell_token"] = validate_hex_to_symbol(offer["TakerGets"]["currency"])
                        of["sell_issuer"] = offer["TakerGets"]["issuer"]
                        of["sell_amount"] = offer["TakerGets"]["value"]
                    elif isinstance(offer["TakerGets"], str):
                        of["sell_token"] = "XRP"
                        of["sell_issuer"] = ""
                        of["sell_amount"] = str(drops_to_xrp(offer["TakerGets"]))                    
                    index += 1
                    best[index] = of

        if best_buy:
            req = BookOffers(taker_gets=sell, taker_pays=buy, ledger_index="validated")
            response = await self.client.request(req)
            result = response.result
            if "offers" in result:
                offers: list = result["offers"]
                # sort offer list and return lowest rate first
                offers.sort(key=lambda object: object["quality"])
                index = 0
                for offer in offers:
                    of = {}
                    of["creator"] = offer["Account"]
                    of["offer_id"] = offer["index"]
                    of["flags"] = offer["Flags"]
                    of["sequence"] = offer["Sequence"] # offer id
                    of["rate"] = offer["quality"]
                    of["creator_liquidity"] = ""
                    if "owner_funds" in offer:
                        of["creator_liquidity"] = offer["owner_funds"] # available amount the offer creator is currently holding
                    if isinstance(offer["TakerPays"], dict):
                        of["buy_token"] = validate_hex_to_symbol(offer["TakerPays"]["currency"])
                        of["buy_issuer"] = offer["TakerPays"]["issuer"]
                        of["buy_amount"] = offer["TakerPays"]["value"]
                    elif isinstance(offer["TakerPays"], str):
                        of["buy_token"] = "XRP"
                        of["buy_issuer"] = ""
                        of["buy_amount"] = str(drops_to_xrp(offer["TakerPays"]))

                    if isinstance(offer["TakerGets"], dict):
                        of["sell_token"] = validate_hex_to_symbol(offer["TakerGets"]["currency"])
                        of["sell_issuer"] = offer["TakerGets"]["issuer"]
                        of["sell_amount"] = offer["TakerGets"]["value"]
                    elif isinstance(offer["TakerGets"], str):
                        of["sell_token"] = "XRP"
                        of["sell_issuer"] = ""
                        of["sell_amount"] = str(drops_to_xrp(offer["TakerGets"]))                    
                    index += 1
                    best[index] = of
        return best


client = JsonRpcClient("https://s.altnet.rippletest.net:51234")

# req = AccountOffers(account="rPd9oB2Kdot9HSsXSeFYpKZUV3vDsBzv73", ledger_index="validated")
# response = client.request(req)
# result = response.result
# print(result)

d = XAMM(client.url)

print(asyncio.run(
    d.sort_best_offer(
        XRP(), IssuedCurrency(issuer="rBZJzEisyXt2gvRWXLxHftFRkd1vJEpBQP", currency="USD"), best_buy=True
    )
))