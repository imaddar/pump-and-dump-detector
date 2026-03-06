import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

import pandas as pd

from ingestion import etherscan_fetch


class BuildWindowTests(unittest.TestCase):
    def test_build_window_uses_wider_default_lookback(self) -> None:
        pump_date = datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc)

        start_ts, end_ts = etherscan_fetch.build_window(pump_date)

        self.assertEqual(end_ts - start_ts, 168 * 60 * 60)


class ContractLookupTests(unittest.TestCase):
    def test_contract_lookup_prefers_exact_symbol_match(self) -> None:
        search_response = Mock(status_code=200)
        search_response.json.return_value = {
            "coins": [
                {"id": "bread", "symbol": "BRD"},
                {"id": "weird-other-match", "symbol": "BRO"},
            ]
        }
        detail_response = Mock(status_code=200)
        detail_response.json.return_value = {"platforms": {"ethereum": "0xabc"}}

        session = Mock()
        session.get.side_effect = [search_response, detail_response]

        contract = etherscan_fetch.get_contract_address("BRD", session=session, sleeper=lambda _: None)

        self.assertEqual(contract, "0xabc")
        detail_call = session.get.call_args_list[1]
        self.assertIn("/bread", detail_call.args[0])


class TransferFetchTests(unittest.TestCase):
    def test_fetch_paginates_until_end_of_window(self) -> None:
        page_one = [
            {"hash": "1", "timeStamp": "100"},
            {"hash": "2", "timeStamp": "200"},
        ]
        page_two = [
            {"hash": "3", "timeStamp": "250"},
            {"hash": "4", "timeStamp": "350"},
        ]
        page_three = []

        fetch_page = Mock(side_effect=[page_one, page_two, page_three])

        original_fetch = etherscan_fetch.fetch_token_transfer_page
        etherscan_fetch.fetch_token_transfer_page = fetch_page
        try:
            transfers = etherscan_fetch.get_token_transfers(
                "0xabc",
                start_ts=150,
                end_ts=300,
                sleeper=lambda _: None,
                page_size=2,
                page_limit=5,
            )
        finally:
            etherscan_fetch.fetch_token_transfer_page = original_fetch

        self.assertEqual([tx["hash"] for tx in transfers], ["2", "3"])
        self.assertEqual(fetch_page.call_count, 2)


class EventParsingTests(unittest.TestCase):
    def test_parse_event_row_preserves_missing_pump_date(self) -> None:
        row = pd.Series(
            {
                "Date": "2019-01-02T15:44:53Z",
                "Currency": "BRD",
                "success": 0,
                "pump_date": float("nan"),
            }
        )

        parsed = etherscan_fetch.parse_event_row(row)

        self.assertEqual(parsed.currency, "BRD")
        self.assertIsNone(parsed.pump_date)


if __name__ == "__main__":
    unittest.main()
