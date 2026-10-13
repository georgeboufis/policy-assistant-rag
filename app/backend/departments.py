"""Which department each document belongs to.

The documents in pipeline are not labelled, but they fall into five groups cleanly
enough that a question can be attributed to a department without guessing - and
without asking a model, which would cost a request per question and could be wrong.

A question's department comes from the documents the SEARCH found, not from the words
of the question:

    answered  -> the departments of the files the model actually cited
    refused   -> the department of the closest chunk it saw

That second line is the useful one. A refusal still tells you which part of the company
somebody was asking about, so "six people asked Facilities something we could not
answer" becomes visible - which is a gap in the documents, not in the assistant.

To add a document, put its file name here. Anything unlisted is reported as "other",
so a new file shows up as unattributed rather than silently vanishing from the totals.
"""

DEPARTMENTS = {
    "hr": [
        "leave_policy.md",            # annual, sick, parental, unpaid leave
        "remote_work_policy.pdf",     # eligibility, hours, ending the arrangement
        "new_starter_guide.html",     # onboarding, first day, buddy
    ],
    "finance": [
        "expenses_policy.md",         # what can be claimed, receipts, approvals
        "travel_policy.md",           # when to travel, class of travel, hotels
        "travel_rates.csv",           # per-city allowances and hotel limits
    ],
    "it": [
        "it_security_policy.md",      # passwords, devices, incidents, leaving
        "support_call_transcript.txt",# the service desk call: VPN, access codes, monitors
    ],
    "facilities": [
        "cleaning_contract.docx",     # the cleaning agreement and its clauses
        "cleaning_supplier_email.eml",# the supplier's price change notice
    ],
    "delivery": [
        "quarterly_debrief.pdf",      # the engineering quarter: migration, tickets, hiring
    ],
}

# file name -> department, worked out once
OF_FILE = {
    file_name: department
    for department, file_names in DEPARTMENTS.items()
    for file_name in file_names
}


def department_of(file_name):
    """The department a document belongs to, or "other" if it is not listed."""
    return OF_FILE.get(file_name, "other")


# The order the dashboard lists them in, with anything unlisted last
ORDER = list(DEPARTMENTS) + ["other"]
