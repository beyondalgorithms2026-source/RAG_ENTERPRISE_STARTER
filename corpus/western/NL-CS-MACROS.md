SYNTHETIC

---
id: NL-CS-MACROS
title: Customer Support Reply Macros
doc_type: playbook
jurisdiction: group
classification: Internal
effective: 2026-03-01
supersedes: none
synthetic: true
---

# Customer Support Reply Macros

## Use

These replies are starting points. Agents must edit placeholders, remove irrelevant text and avoid sending a macro that misstates the customer's contract or situation.

### Password reset

**Subject:** Resetting your Northline access

Hi {{first_name}},

Please use the **Forgot password** link on the Northline sign-in page. It will send a time-limited reset link to the email address on your account. If that email does not arrive within 10 minutes, tell us the account email and your organisation name; please do not send us your password.

Thanks,  
Northline Support

### Admin access reset

Hi {{first_name}},

We can help with the admin-access request. Before we change an administrator, we need to verify the request through your organisation's approved account contact. I’ve started that verification and will update this case when it is complete.

Thanks,  
Northline Support

### Invoice copy

Hi {{first_name}},

I can help with an invoice copy. Please confirm the invoice number or billing period. We’ll provide the existing invoice to an authorised billing contact; changes to legal billing details are handled by Finance rather than Support.

Thanks,  
Northline Support

### P1 acknowledgement

Hi {{first_name}},

We’ve classified this as **P1 Critical** based on the production impact you described. Our team is actively investigating. The next customer update will follow the incident cadence, or sooner if we have material new information.

Current impact understood: {{impact_summary}}

Thanks,  
Northline Support

### P2 acknowledgement

Hi {{first_name}},

We’ve classified this as **P2 High**. We understand that {{impact_summary}}. We’re reviewing {{next_step}} and will update you by {{next_update_time}}.

Thanks,  
Northline Support

### Request for diagnostics

Hi {{first_name}},

To narrow this down, could you send the following without including passwords, private keys or full access tokens?

- approximate timestamp and time zone;
- affected user or request identifier;
- steps immediately before the error;
- screenshot or exact error text, with sensitive data redacted.

Thanks,  
Northline Support

### Known incident

Hi {{first_name}},

Your case appears related to the active incident affecting {{service_area}}. We’ve linked your case to the incident record. We’ll keep this case updated using the confirmed incident information rather than speculate on root cause.

Thanks,  
Northline Support

### SLA miss apology

Hi {{first_name}},

I’m sorry we did not respond within the target support window for this case. We have not changed the ticket timestamps. The current status is {{status}}, and the next action is {{next_action}}. We’ll update you again by {{next_update_time}}.

Thanks,  
Northline Support

### Feature request routing

Hi {{first_name}},

Thanks for explaining the use case. I’ve recorded the underlying need and routed it to our product-feedback queue. Submission does not create a delivery commitment or roadmap date, but your example will be available to the product team when they review this area.

Thanks,  
Northline Support

### Refund or credit request

Hi {{first_name}},

I understand why you’re asking for a credit. I’ve recorded the request and routed it to the team that reviews commercial adjustments. I can’t confirm an amount or outcome from Support, but we’ll update you after the review.

Thanks,  
Northline Support

### Waiting for customer

Hi {{first_name}},

We’re waiting on {{requested_information}} to continue the investigation. If you can send that information, we’ll pick the case back up. If we do not hear from you, we’ll follow up once more before closing the case after the normal waiting period.

Thanks,  
Northline Support

### Resolution and closure

Hi {{first_name}},

We believe this is resolved following {{resolution_summary}}. We’ll close the case for now. Reply to this thread if the same issue returns and include the new timestamp so we can compare it with the earlier incident.

Thanks,  
Northline Support
