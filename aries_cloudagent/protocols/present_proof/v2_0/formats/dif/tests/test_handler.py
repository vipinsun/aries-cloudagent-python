from copy import deepcopy
from asynctest import TestCase as AsyncTestCase
from asynctest import mock as async_mock
from marshmallow import ValidationError

from .......core.in_memory import InMemoryProfile
from .......messaging.decorators.attach_decorator import AttachDecorator
from .......storage.vc_holder.base import VCHolder
from .......storage.vc_holder.vc_record import VCRecord
from .......vc.ld_proofs import (
    DocumentLoader,
    Ed25519Signature2018,
    BbsBlsSignature2020,
    BbsBlsSignatureProof2020,
)
from .......vc.tests.document_loader import custom_document_loader
from .......vc.vc_ld.validation_result import PresentationVerificationResult
from .......wallet.base import BaseWallet

from .....dif.pres_exch_handler import DIFPresExchHandler

from ....message_types import (
    ATTACHMENT_FORMAT,
    PRES_20_REQUEST,
    PRES_20,
    PRES_20_PROPOSAL,
)
from ....messages.pres import V20Pres
from ....messages.pres_proposal import V20PresProposal
from ....messages.pres_request import V20PresRequest
from ....messages.pres_format import V20PresFormat
from ....models.pres_exchange import V20PresExRecord

from ...handler import V20PresFormatHandlerError

from .. import handler as test_module
from ..handler import DIFPresFormatHandler

TEST_DID_SOV = "did:sov:LjgpST2rjsoxYegQDRm7EL"
TEST_DID_KEY = "did:key:z6Mkgg342Ycpuk263R9d8Aq6MUaxPn1DDeHyGo38EefXmgDL"

DIF_PRES_REQUEST_A = {
    "presentation_definition": {
        "id": "32f54163-7166-48f1-93d8-ff217bdb0653",
        "submission_requirements": [
            {
                "name": "Citizenship Information",
                "rule": "pick",
                "count": 2,
                "from": "A",
            }
        ],
        "input_descriptors": [
            {
                "id": "citizenship_input_1",
                "name": "EU Driver's License",
                "group": ["A"],
                "schema": [{"uri": "https://example.org/examples/degree.json"}],
                "constraints": {
                    "fields": [
                        {
                            "path": ["$.issuer.id", "$.vc.issuer.id", "$.issuer"],
                            "purpose": "The claim must be from one of the specified issuers",
                            "filter": {
                                "type": "string",
                                "enum": [
                                    "did:example:489398593",
                                    "did:key:zUC72Q7XD4PE4CrMiDVXuvZng3sBvMmaGgNeTUJuzavH2BS7ThbHL9FhsZM9QYY5fqAQ4MB8M9oudz3tfuaX36Ajr97QRW7LBt6WWmrtESe6Bs5NYzFtLWEmeVtvRYVAgjFcJSa",
                                    "did:sov:2wJPyULfLLnYTEFYzByfUR",
                                ],
                            },
                        }
                    ]
                },
            }
        ],
    }
}

DIF_PRES_REQUEST_B = {
    "options": {
        "challenge": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
        "domain": "4jt78h47fh47",
    },
    "presentation_definition": {
        "id": "32f54163-7166-48f1-93d8-ff217bdb0654",
        "submission_requirements": [
            {
                "name": "Citizenship Information",
                "rule": "pick",
                "min": 1,
                "from": "A",
            }
        ],
        "input_descriptors": [
            {
                "id": "citizenship_input_1",
                "name": "EU Driver's License",
                "group": ["A"],
                "schema": [
                    {"uri": "https://www.w3.org/2018/credentials#VerifiableCredential"},
                    {"uri": "https://w3id.org/citizenship#PermanentResidentCard"},
                ],
                "constraints": {
                    "limit_disclosure": "required",
                    "fields": [
                        {
                            "path": ["$.credentialSubject.givenName"],
                            "purpose": "The claim must be from one of the specified issuers",
                            "filter": {
                                "type": "string",
                                "enum": ["JOHN", "CAI"],
                            },
                        }
                    ],
                },
            }
        ],
    },
}

DIF_PRES_PROPOSAL = {
    "input_descriptors": [
        {
            "id": "citizenship_input_1",
            "name": "EU Driver's License",
            "group": ["A"],
            "schema": [
                {"uri": "https://www.w3.org/2018/credentials#VerifiableCredential"},
                {"uri": "https://w3id.org/citizenship#PermanentResidentCard"},
            ],
            "constraints": {
                "fields": [
                    {
                        "path": ["$.issuer.id", "$.vc.issuer.id", "$.issuer"],
                        "purpose": "The claim must be from one of the specified issuers",
                        "filter": {
                            "type": "string",
                            "enum": [
                                "did:example:489398593",
                                "did:key:zUC72Q7XD4PE4CrMiDVXuvZng3sBvMmaGgNeTUJuzavH2BS7ThbHL9FhsZM9QYY5fqAQ4MB8M9oudz3tfuaX36Ajr97QRW7LBt6WWmrtESe6Bs5NYzFtLWEmeVtvRYVAgjFcJSa",
                                "did:sov:2wJPyULfLLnYTEFYzByfUR",
                            ],
                        },
                    }
                ]
            },
        }
    ]
}

DIF_PRES = {
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "type": ["VerifiablePresentation"],
    "verifiableCredential": [
        {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://w3id.org/citizenship/v1",
                "https://w3id.org/security/bbs/v1",
            ],
            "id": "https://issuer.oidp.uscis.gov/credentials/83627465",
            "type": ["PermanentResidentCard", "VerifiableCredential"],
            "credentialSubject": {
                "id": "did:example:b34ca6cd37bbf23",
                "type": ["Person", "PermanentResident"],
                "givenName": "JOHN",
            },
            "issuanceDate": "2010-01-01T19:53:24Z",
            "issuer": "did:key:zUC74bgefTdc43KS1psXgXf4jLaHyaj2qCQqQTXrtmSYGf1PxiJhrH6LGpaBMyj6tqAKmjGyMaS4RfNo2an77vT1HfzJUNPk4H7TCuJvSp4vet4Cu67kn2JSegoQNFSA1tbwU8v",
            "proof": {
                "type": "BbsBlsSignatureProof2020",
                "nonce": "3AuruhJQrXtEgiagiJ+FwVf2S0SnzUDJvnO61YecQsJ7ImR1mPcoVjJJ0HOhfkFpoYI=",
                "proofValue": "ABkBuAaPlP5A7JWY78Xf69oBnsMLcD1RXbIFYhcLoXPXW12CG9glnnqnPLsGri5xsA3LcP0kg74X+sAjKXGRGy3uvp412Dm0FuohYNboQcLne5KOAa5AxU4bjmwQsxdfduVqhriro1N+YTkuB4SMmO/5ooL0N3OHsYdExg7nSzWqmZoqgp+3CwIxF0a/oyKTcxJORuIqAAAAdInlL9teSIX49NJGEZfBO7IrdjT2iggH/G0AlPWoEvrWIbuCRQ69K83n5o7oJVjqhAAAAAIaVmlAD6+FEKA4eg0OaWOKPrd5Kq8rv0vIwjJ71egxll0Fqq4zDWQ/+yl3Pteh0Wyuyvpm19/sj6tiCWj4PkA+rpxtR2bXpnrCTKUffFFNBjVvVziXDS0KWkGUB7XU9mjUa4USC7Iub3bZZCnFjQA5AAAADzkGwGD837r33e7OTrGEti8eAkvFDcyCgA4ck/X+5HJjAJclHWbl4SNQR8CiNZyzJpvxW+jbNBcwmEvocYArddk3F78Ki0Qnp6aU9eDgfOOx1iW2BXLUjrhq5I2hP5/WQF3CEDYRjczGjzM9T8/coeC36YAp0zJunIXUKb8SPDSOISafibYRYFB4xhlWKXWloDelafyujOBST8KZNM8FmF4DSbXrO8vmZbjuR/8ntUcUK7X2rNbuZ3M5eWZDF8pL+SA9gQitKfPHEocoYAdhgEAM7ZNAJ+TgOcx9gtZIhDWKDNnFxIeoOAylbD1xZd9xbWtq3Bk3R79xqsKxFRJRNxk/9b6fJruP292+qM5lxcZ1jUz/dJUYFI93hH4Mso75CjGRN78MAY9SNifl6H8qcxTpBn4332LlFhRznLbtnc4YSWA/fvVqaN9h2zCH/6AdbLKXGffV34EF7DadwJsi9jsc+YlSMn6qaIUIDTdGLwh4KKpSH5bVbg/mVCcXPTJplFgYwRsOdiQbZY/740dJyo1lPjQ0Lvdio8W2M8c73ujeJU70CNLkgjJAMUPGrCFtGxBH2eeLBQ0P95qRZAIcJ7U0MibZLaRjoUOuTla5BIt2038PJ6XhcY6BEJaLyJOPEQ==",
                "verificationMethod": "did:key:zUC74bgefTdc43KS1psXgXf4jLaHyaj2qCQqQTXrtmSYGf1PxiJhrH6LGpaBMyj6tqAKmjGyMaS4RfNo2an77vT1HfzJUNPk4H7TCuJvSp4vet4Cu67kn2JSegoQNFSA1tbwU8v#zUC74bgefTdc43KS1psXgXf4jLaHyaj2qCQqQTXrtmSYGf1PxiJhrH6LGpaBMyj6tqAKmjGyMaS4RfNo2an77vT1HfzJUNPk4H7TCuJvSp4vet4Cu67kn2JSegoQNFSA1tbwU8v",
                "proofPurpose": "assertionMethod",
                "created": "2021-05-05T15:22:30.523465",
            },
        }
    ],
    "presentation_submission": {
        "id": "a5fcfe44-2c30-497d-af02-98e539da9a0f",
        "definition_id": "32f54163-7166-48f1-93d8-ff217bdb0653",
        "descriptor_map": [
            {
                "id": "citizenship_input_1",
                "format": "ldp_vp",
                "path": "$.verifiableCredential[0]",
            }
        ],
    },
    "proof": {
        "type": "Ed25519Signature2018",
        "verificationMethod": "did:sov:4QxzWk3ajdnEA37NdNU5Kt#key-1",
        "created": "2021-05-05T15:23:03.023971",
        "proofPurpose": "authentication",
        "challenge": "40429d49-5e8f-4ffc-baf8-e332412f1247",
        "jws": "eyJhbGciOiAiRWREU0EiLCAiYjY0IjogZmFsc2UsICJjcml0IjogWyJiNjQiXX0..2uBYmg7muE9ZPVeAGo_ibVfLkCjf2hGshr2o5i8pAwFyNBM-kDHXofuq1MzJgb19wzb01VIu91hY_ajjt9KFAA",
    },
}

TEST_CRED = {
    "@context": [
        "https://www.w3.org/2018/credentials/v1",
        "https://w3id.org/citizenship/v1",
        "https://w3id.org/security/bbs/v1",
    ],
    "id": "https://issuer.oidp.uscis.gov/credentials/83627465",
    "type": ["VerifiableCredential", "PermanentResidentCard"],
    "issuer": "did:key:zUC76eX863NT1BEFYEfSMRY4CSVwRmRdKBtv3cwTwytDXNEAvJxFr3GBjkpKRs3xg9FznUhxXkwDLLu7UjDnetSQNvGiT1ivHdDFByZdXoWLYpDDRph5eZDXTGNweuq3Z8uAo3o",
    "identifier": "83627465",
    "name": "Permanent Resident Card",
    "description": "Government of Example Permanent Resident Card.",
    "issuanceDate": "2010-01-01T19:53:24Z",
    "expirationDate": "2029-12-03T12:19:52Z",
    "credentialSubject": {
        "id": "did:sov:4QxzWk3ajdnEA37NdNU5Kt",
        "type": ["PermanentResident", "Person"],
        "givenName": "JOHN",
        "familyName": "SMITH",
        "gender": "Male",
        "image": "data:image/png;base64,iVBORw0KGgokJggg==",
        "residentSince": "2015-01-01",
        "lprCategory": "C09",
        "lprNumber": "999-999-999",
        "commuterClassification": "C1",
        "birthCountry": "Bahamas",
        "birthDate": "1958-07-17",
    },
}


class TestDIFFormatHandler(AsyncTestCase):
    async def setUp(self):
        self.holder = async_mock.MagicMock()
        self.wallet = async_mock.MagicMock(BaseWallet, autospec=True)

        self.session = InMemoryProfile.test_session(
            bind={VCHolder: self.holder, BaseWallet: self.wallet}
        )
        self.profile = self.session.profile
        self.context = self.profile.context
        setattr(
            self.profile, "session", async_mock.MagicMock(return_value=self.session)
        )

        # Set custom document loader
        self.context.injector.bind_instance(DocumentLoader, custom_document_loader)

        self.handler = DIFPresFormatHandler(self.profile)
        assert self.handler.profile

    def test_validate_fields(self):
        self.handler.validate_fields(PRES_20, DIF_PRES)
        self.handler.validate_fields(PRES_20_PROPOSAL, DIF_PRES_PROPOSAL)
        self.handler.validate_fields(PRES_20_REQUEST, DIF_PRES_REQUEST_A)
        self.handler.validate_fields(PRES_20_REQUEST, DIF_PRES_REQUEST_B)

        with self.assertRaises(ValidationError):
            incorrect_pres = DIF_PRES.copy()
            incorrect_pres.pop("@context")
            self.handler.validate_fields(PRES_20, incorrect_pres)

    async def test_get_all_suites(self):
        suites = await self.handler._get_all_suites(self.wallet)
        assert len(suites) == 3
        types = [Ed25519Signature2018, BbsBlsSignature2020, BbsBlsSignatureProof2020]
        for suite in suites:
            assert type(suite) in types

    async def test_create_bound_request(self):
        dif_proposal_dict = {
            "input_descriptors": [
                {
                    "id": "citizenship_input_1",
                    "name": "EU Driver's License",
                    "group": ["A"],
                    "schema": [
                        {
                            "uri": "https://www.w3.org/2018/credentials#VerifiableCredential"
                        }
                    ],
                    "constraints": {
                        "limit_disclosure": "required",
                        "fields": [
                            {
                                "path": ["$.credentialSubject.givenName"],
                                "purpose": "The claim must be from one of the specified issuers",
                                "filter": {"type": "string", "enum": ["JOHN", "CAI"]},
                            }
                        ],
                    },
                }
            ]
        }
        dif_pres_proposal = V20PresProposal(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_PROPOSAL][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            proposals_attach=[
                AttachDecorator.data_json(dif_proposal_dict, ident="dif")
            ],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_proposal=dif_pres_proposal,
            verified="false",
            auto_present=True,
            error_msg="error",
        )
        output = await self.handler.create_bound_request(pres_ex_record=record)
        assert isinstance(output[0], V20PresFormat) and isinstance(
            output[1], AttachDecorator
        )

    async def test_create_pres(self):
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(DIF_PRES_REQUEST_B, ident="dif")
            ],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            verified="false",
            auto_present=True,
            error_msg="error",
        )

        with async_mock.patch.object(
            DIFPresExchHandler,
            "create_vp",
            async_mock.CoroutineMock(),
        ) as mock_create_vp:
            mock_create_vp.return_value = DIF_PRES
            output = await self.handler.create_pres(record, {})
            assert isinstance(output[0], V20PresFormat) and isinstance(
                output[1], AttachDecorator
            )
            assert output[1].data.json_ == DIF_PRES

    async def test_create_pres_pd_schema_uri(self):
        dif_pres_req = deepcopy(DIF_PRES_REQUEST_B)
        dif_pres_req["presentation_definition"]["input_descriptors"][0]["schema"][0][
            "uri"
        ] = "test.json"
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(dif_pres_req, ident="dif")
            ],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            verified="false",
            auto_present=True,
            error_msg="error",
        )
        request_data = {}
        with async_mock.patch.object(
            DIFPresExchHandler,
            "create_vp",
            async_mock.CoroutineMock(),
        ) as mock_create_vp:
            mock_create_vp.return_value = DIF_PRES
            output = await self.handler.create_pres(record, request_data)
            assert isinstance(output[0], V20PresFormat) and isinstance(
                output[1], AttachDecorator
            )
            assert output[1].data.json_ == DIF_PRES

    async def test_create_pres_prover_proof_spec(self):
        dif_pres_spec = deepcopy(DIF_PRES_REQUEST_A)
        dif_pres_spec["issuer_id"] = "test123"
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(DIF_PRES_REQUEST_B, ident="dif")
            ],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            verified="false",
            auto_present=True,
            error_msg="error",
        )
        request_data = {}
        request_data["dif"] = dif_pres_spec
        with async_mock.patch.object(
            DIFPresExchHandler,
            "create_vp",
            async_mock.CoroutineMock(),
        ) as mock_create_vp:
            mock_create_vp.return_value = DIF_PRES
            output = await self.handler.create_pres(record, request_data)
            assert isinstance(output[0], V20PresFormat) and isinstance(
                output[1], AttachDecorator
            )
            assert output[1].data.json_ == DIF_PRES

    async def test_create_pres_prover_proof_spec_with_record_ids(self):
        dif_pres_spec = deepcopy(DIF_PRES_REQUEST_A)
        dif_pres_spec["issuer_id"] = "test123"
        dif_pres_spec["record_ids"] = ["test1"]
        cred = VCRecord(
            contexts=[
                "https://www.w3.org/2018/credentials/v1",
                "https://www.w3.org/2018/credentials/examples/v1",
            ],
            expanded_types=[
                "https://www.w3.org/2018/credentials#VerifiableCredential",
                "https://example.org/examples#UniversityDegreeCredential",
            ],
            issuer_id="https://example.edu/issuers/565049",
            subject_ids=[
                "did:sov:LjgpST2rjsoxYegQDRm7EL",
                "did:key:z6Mkgg342Ycpuk263R9d8Aq6MUaxPn1DDeHyGo38EefXmgDL",
            ],
            proof_types=["BbsBlsSignature2020"],
            schema_ids=["https://example.org/examples/degree.json"],
            cred_value={"...": "..."},
            given_id="http://example.edu/credentials/3732",
            cred_tags={"some": "tag"},
            record_id="test1",
        )
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(DIF_PRES_REQUEST_B, ident="dif")
            ],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            verified="false",
            auto_present=True,
            error_msg="error",
        )
        request_data = {}
        request_data["dif"] = dif_pres_spec

        self.context.injector.bind_instance(
            VCHolder,
            async_mock.MagicMock(
                retrieve_credential_by_id=async_mock.CoroutineMock(return_value=cred)
            ),
        )

        with async_mock.patch.object(
            DIFPresExchHandler,
            "create_vp",
            async_mock.CoroutineMock(),
        ) as mock_create_vp:
            mock_create_vp.return_value = DIF_PRES
            output = await self.handler.create_pres(record, request_data)

    async def test_create_pres_no_challenge(self):
        dif_pres_req = deepcopy(DIF_PRES_REQUEST_B)
        del dif_pres_req["options"]["challenge"]
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(dif_pres_req, ident="dif")
            ],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            verified="false",
            auto_present=True,
            error_msg="error",
        )
        request_data = {}
        with async_mock.patch.object(
            DIFPresExchHandler,
            "create_vp",
            async_mock.CoroutineMock(),
        ) as mock_create_vp:
            mock_create_vp.return_value = DIF_PRES
            output = await self.handler.create_pres(record, request_data)
            assert isinstance(output[0], V20PresFormat) and isinstance(
                output[1], AttachDecorator
            )
            assert output[1].data.json_ == DIF_PRES

    async def test_create_pres_storage_not_found(self):
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(DIF_PRES_REQUEST_B, ident="dif")
            ],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            verified="false",
            auto_present=True,
            error_msg="error",
        )

        self.context.injector.bind_instance(
            VCHolder,
            async_mock.MagicMock(
                search_credentials=async_mock.MagicMock(
                    return_value=async_mock.MagicMock(
                        fetch=async_mock.CoroutineMock(
                            side_effect=test_module.StorageNotFoundError()
                        )
                    )
                )
            ),
        )
        with self.assertRaises(V20PresFormatHandlerError):
            await self.handler.create_pres(record)

    async def test_create_pres_pd_claim_format_ed255(self):
        test_pd = deepcopy(DIF_PRES_REQUEST_B)
        test_pd["presentation_definition"]["format"] = {
            "ldp_vp": {"proof_type": ["Ed25519Signature2018"]}
        }
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(test_pd, ident="dif")
            ],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            verified="false",
            auto_present=True,
            error_msg="error",
        )

        with async_mock.patch.object(
            DIFPresExchHandler,
            "create_vp",
            async_mock.CoroutineMock(),
        ) as mock_create_vp:
            mock_create_vp.return_value = DIF_PRES
            output = await self.handler.create_pres(record, {})
            assert isinstance(output[0], V20PresFormat) and isinstance(
                output[1], AttachDecorator
            )
            assert output[1].data.json_ == DIF_PRES

    async def test_create_pres_pd_claim_format_bls12381g2(self):
        test_pd = deepcopy(DIF_PRES_REQUEST_B)
        test_pd["presentation_definition"]["format"] = {
            "ldp_vp": {"proof_type": ["BbsBlsSignature2020"]}
        }
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(test_pd, ident="dif")
            ],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            verified="false",
            auto_present=True,
            error_msg="error",
        )

        with async_mock.patch.object(
            DIFPresExchHandler,
            "create_vp",
            async_mock.CoroutineMock(),
        ) as mock_create_vp:
            mock_create_vp.return_value = DIF_PRES
            output = await self.handler.create_pres(record, {})
            assert isinstance(output[0], V20PresFormat) and isinstance(
                output[1], AttachDecorator
            )
            assert output[1].data.json_ == DIF_PRES

    async def test_verify_pres(self):
        dif_pres = V20Pres(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20][V20PresFormat.Format.DIF.api],
                )
            ],
            presentations_attach=[AttachDecorator.data_json(DIF_PRES, ident="dif")],
        )
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(DIF_PRES_REQUEST_B, ident="dif")
            ],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            pres=dif_pres,
            verified="false",
            auto_present=True,
            error_msg="error",
        )

        with async_mock.patch.object(
            test_module,
            "verify_presentation",
            async_mock.CoroutineMock(
                return_value=PresentationVerificationResult(verified=True)
            ),
        ) as mock_vr:
            output = await self.handler.verify_pres(record)
            assert output.verified

    async def test_verify_pres_no_challenge(self):
        test_pd = deepcopy(DIF_PRES_REQUEST_B)
        del test_pd["options"]["challenge"]
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(test_pd, ident="dif")
            ],
        )
        dif_pres = V20Pres(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20][V20PresFormat.Format.DIF.api],
                )
            ],
            presentations_attach=[AttachDecorator.data_json(DIF_PRES, ident="dif")],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            pres=dif_pres,
            verified="false",
            auto_present=True,
            error_msg="error",
        )

        with self.assertRaises(V20PresFormatHandlerError):
            await self.handler.verify_pres(record)

    async def test_verify_pres_invalid_challenge(self):
        test_pd = deepcopy(DIF_PRES_REQUEST_B)
        del test_pd["options"]
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(test_pd, ident="dif")
            ],
        )
        dif_pres = V20Pres(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20][V20PresFormat.Format.DIF.api],
                )
            ],
            presentations_attach=[AttachDecorator.data_json(DIF_PRES, ident="dif")],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            pres=dif_pres,
            verified="false",
            auto_present=True,
            error_msg="error",
        )

        with self.assertRaises(V20PresFormatHandlerError):
            await self.handler.verify_pres(record)

    async def test_create_pres_cred_v1_context_schema_uri(self):
        test_pd = deepcopy(DIF_PRES_REQUEST_B)
        test_pd["presentation_definition"]["input_descriptors"][0]["schema"].pop(1)
        dif_pres_request = V20PresRequest(
            formats=[
                V20PresFormat(
                    attach_id="dif",
                    format_=ATTACHMENT_FORMAT[PRES_20_REQUEST][
                        V20PresFormat.Format.DIF.api
                    ],
                )
            ],
            request_presentations_attach=[
                AttachDecorator.data_json(test_pd, ident="dif")
            ],
        )
        record = V20PresExRecord(
            pres_ex_id="pxid",
            thread_id="thid",
            connection_id="conn_id",
            initiator="init",
            role="role",
            state="state",
            pres_request=dif_pres_request,
            verified="false",
            auto_present=True,
            error_msg="error",
        )

        with self.assertRaises(V20PresFormatHandlerError):
            await self.handler.create_pres(record)

    async def test_process_vcrecords_return_list(self):
        cred_list = [
            VCRecord(
                contexts=[
                    "https://www.w3.org/2018/credentials/v1",
                    "https://www.w3.org/2018/credentials/examples/v1",
                ],
                expanded_types=[
                    "https://www.w3.org/2018/credentials#VerifiableCredential",
                    "https://example.org/examples#UniversityDegreeCredential",
                ],
                issuer_id="https://example.edu/issuers/565049",
                subject_ids=[
                    "did:sov:LjgpST2rjsoxYegQDRm7EL",
                    "did:key:z6Mkgg342Ycpuk263R9d8Aq6MUaxPn1DDeHyGo38EefXmgDL",
                ],
                proof_types=["BbsBlsSignature2020"],
                schema_ids=["https://example.org/examples/degree.json"],
                cred_value={"...": "..."},
                given_id="http://example.edu/credentials/3732",
                cred_tags={"some": "tag"},
                record_id="test1",
            ),
            VCRecord(
                contexts=[
                    "https://www.w3.org/2018/credentials/v1",
                    "https://www.w3.org/2018/credentials/examples/v1",
                ],
                expanded_types=[
                    "https://www.w3.org/2018/credentials#VerifiableCredential",
                    "https://example.org/examples#UniversityDegreeCredential",
                ],
                issuer_id="https://example.edu/issuers/565049",
                subject_ids=[
                    "did:sov:LjgpST2rjsoxYegQDRm7EL",
                    "did:key:z6Mkgg342Ycpuk263R9d8Aq6MUaxPn1DDeHyGo38EefXmgDL",
                ],
                proof_types=["BbsBlsSignature2020"],
                schema_ids=["https://example.org/examples/degree.json"],
                cred_value={"...": "..."},
                given_id="http://example.edu/credentials/3732",
                cred_tags={"some": "tag"},
                record_id="test2",
            ),
        ]
        record_ids = {"test1"}
        (
            returned_cred_list,
            returned_record_ids,
        ) = await self.handler.process_vcrecords_return_list(cred_list, record_ids)
        assert len(returned_cred_list) == 1
        assert len(returned_record_ids) == 2
        assert returned_cred_list[0].record_id == "test2"
