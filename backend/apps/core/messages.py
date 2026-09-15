"""
BizYangu — Centralized message strings (English-first, keyed for i18n).

All user-facing error messages, success notifications, and UI text are defined
here rather than inline in view code. This enables:
- Single-pass language corpus swap (English → Swahili, etc.) without touching views
- Consistency across the API
- Easier testing and logging

Usage in views:
    from apps.core.messages import MESSAGES
    return Response({'detail': MESSAGES['BUSINESS_NOT_FOUND']}, status=404)

To add i18n support, create a parallel dict MESSAGES_SW with Swahili strings,
and select based on user language preference or request header.
"""

# English (default)
MESSAGES = {
    # Authentication & Authorization
    'INVALID_OTP': 'Invalid OTP. Please try again.',
    'OTP_EXPIRED': 'OTP has expired. Request a new one.',
    'OTP_SENT': 'OTP sent to {phone}.',
    'OTP_NOT_FOUND': 'OTP not found or has expired.',
    'GOOGLE_SIGNIN_NOT_CONFIGURED': 'Google sign-in is not available right now. Please use your phone number instead.',
    'GOOGLE_SIGNIN_INVALID_TOKEN': 'Could not verify your Google sign-in. Please try again.',
    'GOOGLE_SIGNIN_EMAIL_NOT_VERIFIED': 'Your Google email is not verified. Please verify it with Google first.',
    'OTP_TOO_MANY_ATTEMPTS': 'Too many attempts. Request a new OTP.',
    'OTP_INVALID_WITH_ATTEMPTS': 'Invalid OTP. {remaining} attempts remaining.',
    'LOGIN_FAILED': 'Login failed. Please check your credentials.',
    'UNAUTHORIZED': 'You do not have permission to perform this action.',
    'INVALID_TOKEN': 'Invalid or expired token.',
    'TOKEN_REFRESH_FAILED': 'Unable to refresh token. Please log in again.',
    'REFRESH_TOKEN_NOT_FOUND': 'Refresh token not found.',
    'REFRESH_TOKEN_INVALID': 'Refresh token is invalid or has expired.',
    'TOKEN_REFRESHED': 'Token refreshed.',
    'LOGGED_OUT': 'You have been signed out.',
    'DEV_BYPASS_MODE': 'Dev mode is on: use OTP 000000.',
    'PIN_SET': 'PIN set. You can use it to log in next time.',
    'PIN_INVALID_FORMAT': 'PIN must be 4-6 digits.',
    'PIN_SESSION_NOT_FOUND': 'Your session has expired. Please log in with OTP.',
    'PIN_SESSION_INVALID': 'Your session is no longer valid. Please log in with OTP.',
    'PIN_NOT_SET': 'No PIN is set for this account yet.',
    'PIN_LOCKED': 'Too many incorrect attempts. Please log in with OTP.',
    'PIN_INCORRECT': 'Incorrect PIN. {remaining} attempts remaining.',
    'PIN_VERIFIED': 'Welcome back.',

    # Business
    'BUSINESS_NOT_FOUND': 'Business not found.',
    'BUSINESS_NOT_REGISTERED': 'Your business is not registered yet.',
    'BUSINESS_ALREADY_REGISTERED': 'Your business is already registered.',
    'BUSINESS_NAME_REQUIRED': 'Business name is required.',
    'INVALID_BUSINESS': 'Invalid business ID.',
    'BUSINESS_CREATED': 'Business created successfully.',
    'BUSINESS_UPDATED': 'Business updated successfully.',

    # Staff & Invites
    'INVALID_ROLE': 'Invalid role. Use CASHIER or MANAGER.',
    'TOKEN_AND_PHONE_REQUIRED': 'A valid invite link is required.',
    'FEATURE_NOT_IMPLEMENTED': 'This feature will be completed with the StaffInvite model.',
    'BUSINESS_NOT_FOUND_CREATE_FIRST': 'Business not found. Create a business first.',
    'OWNER_PERMISSION_REQUIRED': 'This change requires owner permission.',
    'STAFF_NOT_FOUND': 'Staff member not found.',
    'CANNOT_REMOVE_SELF': 'You cannot remove yourself.',
    'STAFF_REMOVED': 'Staff member removed.',
    'INVITE_INVALID': 'This invite link is invalid.',
    'INVITE_EXPIRED': 'This invite link has expired. Ask the owner for a new one.',
    'INVITE_ALREADY_USED': 'This invite link has already been used.',
    'INVITE_ACCEPTED': "You've joined the business.",
    'USER_ALREADY_HAS_BUSINESS': 'Your account is already linked to a business.',

    # Products & Catalog
    'PRODUCT_NOT_FOUND': 'Product not found.',
    'PRODUCT_ALREADY_EXISTS': 'Product with this SKU already exists.',
    'INVALID_PRICE': 'Price must be greater than zero.',
    'INVALID_QUANTITY': 'Quantity must be greater than zero.',
    'PRODUCT_CREATED': 'Product created successfully.',
    'PRODUCT_UPDATED': 'Product updated successfully.',
    'PRODUCT_DELETED': 'Product deleted successfully.',
    'PRODUCTS_NOT_FOUND': 'No products found.',
    'CATEGORY_WRONG_BUSINESS': 'This category does not belong to your business.',

    # Shared product identity (barcode resolve/candidate/verify)
    'GLOBAL_PRODUCT_ALREADY_EXISTS': 'This barcode is already known. Try scanning again.',
    'GLOBAL_PRODUCT_NOT_FOUND': 'No known product found for this barcode.',
    'CSV_FILE_REQUIRED': 'Upload a CSV file (key: "file").',
    'CSV_INVALID_FORMAT': 'File must be in .csv format.',
    'CSV_FILE_TOO_LARGE': 'File too large. Limit is {max_size}MB.',
    'STOCK_CANNOT_BE_NEGATIVE': 'Stock cannot be below zero.',

    # Transactions
    'TRANSACTION_NOT_FOUND': 'Transaction not found.',
    'RECEIPT_NOT_FOUND': "No receipt found with that number. Check it's typed correctly.",
    'TRANSACTION_VOIDED': 'Transaction voided successfully.',
    'TRANSACTION_ALREADY_VOIDED': 'This transaction has already been voided.',
    'REFUND_ORIGINAL_NOT_SALE': 'Only a SALE transaction can be refunded.',
    'REFUND_ORIGINAL_VOIDED': 'Cannot refund a voided transaction.',
    'REFUND_ORIGINAL_NOT_CONFIRMED': 'Cannot refund a sale whose payment is not confirmed yet.',
    'REFUND_AMOUNT_EXCEEDS_REMAINING': 'Cannot refund KES {amount} — only KES {remaining} is left refundable on this sale.',
    'REFUND_PROCESSED': 'Refund processed successfully.',
    'INSUFFICIENT_STOCK': 'Insufficient stock for this product.',
    'INSUFFICIENT_STOCK_DETAIL': "Not enough stock for '{name}'. Remaining: {remaining}, requested: {requested}.",
    'PRODUCT_NOT_FOUND_WITH_ID': 'Product {product_id} not found.',
    'UNRECONCILED_GROUP_NOT_FOUND': 'No unresolved custom sale items found with that name — it may have already been resolved.',
    'MIXED_PAYMENT_AMOUNTS_MISMATCH': 'The cash, M-Pesa, and credit amounts must add up to the total (KES {total}).',
    'CREDIT_CUSTOMER_REQUIRED': "Add the customer's name to record this as credit.",
    'CUSTOMER_NOT_FOUND': 'Customer not found.',
    'ADJUSTMENT_NEGATIVE_STOCK': 'This change would take stock below zero.',
    'DATA_HEALTH_REASON_COST_PRICE': '{count} product(s) are missing a cost price — add it to see accurate profit.',
    'DATA_HEALTH_REASON_TAXONOMY_DEPTH': 'Only {percentage}% of your catalog has brand-level detail (e.g. "Jameson" instead of "Whisky").',
    'DATA_HEALTH_REASON_RECONCILIATION': '{count} sale item(s) still need to be linked to a real product in Stock.',
    'MILESTONE_HIGHEST_DAY_SALES': 'Best day yet — KES {value} in sales.',
    'MILESTONE_FULLY_RECONCILED_WEEK': 'A full week with every sale item matched to a real product.',
    'MILESTONE_CONFIDENCE_TO_ACT': "Your profit report is now fully accurate — {percentage}% of your catalog has a cost price.",
    'STOCK_MOVEMENT_REFUND_NOTE': 'Refund: {reference}',
    'SALE_CREATED': 'Sale recorded successfully.',
    'SALE_VOIDED': 'Sale voided.',
    'INVALID_PAYMENT_METHOD': 'Invalid payment method.',
    'PAYMENT_PENDING': 'Payment is pending.',
    'PAYMENT_CONFIRMED': 'Payment confirmed.',
    'PAYMENT_FAILED': 'Payment failed. Please try again.',
    'TRANSACTION_CREATED': 'Transaction created successfully.',

    # Stock & Inventory
    'STOCK_IN_RECORDED': 'Stock received and recorded.',
    'STOCK_LOSS_RECORDED': 'Stock loss recorded.',
    'STOCK_COUNT_SUBMITTED': 'Stock count submitted successfully.',
    'STOCK_COUNT_NOTE': 'Physical count: {quantity}',
    'LOW_STOCK_THRESHOLD_SET': 'Low stock threshold updated.',
    'STOCK_UPDATED': 'Stock updated successfully.',

    # Payments & M-Pesa
    'PAYMENT_NOT_FOUND': 'Payment not found.',
    'STK_PUSH_SENT': 'Payment prompt sent to phone.',
    'STK_PUSH_FAILED': 'Unable to send payment prompt. Please try again.',
    'C2B_REGISTRATION_FAILED': 'C2B registration failed.',
    'CALLBACK_PROCESSED': 'Callback processed successfully.',
    'TRANSACTION_NOT_MPESA': 'This transaction is not an M-Pesa payment.',
    'TRANSACTION_ALREADY_PROCESSED': 'This transaction has already been processed.',
    'STK_REQUEST_ALREADY_PENDING': 'An STK Push request is already pending for this transaction.',
    'STK_REQUEST_NOT_FOUND': 'Request not found.',
    'MPESA_TRANSACTION_NOT_FOUND': 'M-Pesa transaction not found.',

    # Subscription billing (company M-Pesa, not a business sale)
    'SUBSCRIPTION_PAYMENT_SENT': 'Payment prompt sent to phone.',
    'SUBSCRIPTION_PAYMENT_FAILED': 'Unable to send payment prompt. Please try again.',
    'SUBSCRIPTION_PAYMENT_ALREADY_PENDING': 'A subscription payment request is already pending.',
    'SUBSCRIPTION_PAYMENT_NOT_FOUND': 'Subscription payment not found.',
    'SUBSCRIPTION_PAYMENT_CONFIRMED': 'Subscription payment confirmed.',

    # Business M-Pesa credentials (per-business Daraja app)
    'MPESA_CREDENTIALS_SAVED': 'M-Pesa settings saved.',
    'MPESA_CREDENTIALS_NOT_CONFIGURED': 'M-Pesa credentials are not fully filled in yet.',
    'MPESA_CREDENTIALS_VERIFIED': 'M-Pesa credentials verified and activated.',
    'MPESA_CREDENTIALS_VERIFY_FAILED': 'Could not verify these M-Pesa credentials. Please check them and try again.',
    'MPESA_CREDENTIALS_DEACTIVATED': 'Your own M-Pesa till has been switched off — sales will use the shared BizYangu number again.',

    # Notifications & Push
    'DEVICE_REGISTERED': 'Device registered for notifications.',
    'DEVICE_UNREGISTERED': 'Device unregistered.',
    'NOTIFICATION_SENT': 'Notification sent.',
    'TOKEN_REQUIRED': 'Token is required.',
    'OUT_OF_STOCK_TITLE': 'Out of Stock',
    'LOW_STOCK_TITLE': 'Low Stock',
    'OUT_OF_STOCK_BODY': '{product} is completely out of stock. Restock soon.',
    'LOW_STOCK_BODY': '{product} has only {stock} {unit} left — below the threshold of {threshold}.',

    # Reports
    'REPORT_GENERATED': 'Report generated successfully.',
    'REPORT_NOT_FOUND': 'Report not found.',
    'INVALID_DATE_FORMAT': 'Invalid date. Use format YYYY-MM-DD.',
    'INVALID_DATE_RANGE': 'Start date must be on or before the end date.',
    'DATE_RANGE_TOO_LARGE': 'Date range cannot be longer than {max_days} days.',

    # Validation Errors
    'REQUIRED_FIELD': 'This field is required.',
    'INVALID_FORMAT': 'Invalid format.',
    'DUPLICATE_ENTRY': 'This entry already exists.',
    'NOT_FOUND': 'Not found.',
    'INVALID_PHONE_NUMBER': 'Invalid phone number.',
    'INVALID_PHONE_NUMBER_FORMAT': 'Invalid phone number. Use format: +254XXXXXXXXX or 07XXXXXXXX',
    'FIRST_NAME_REQUIRED': 'First name is required.',
    'LAST_NAME_REQUIRED': 'Last name is required.',
    'EMAIL_ALREADY_IN_USE': 'That email address is already in use by another account.',
    'INVALID_EMAIL_FORMAT': 'Please enter a valid email address.',
    'ACCOUNT_UPDATED': 'Account details updated.',

    # Customers & Credit (Phase 12)
    'CUSTOMER_PHONE_IN_USE': 'A customer with this phone number already exists.',
    'SETTLEMENT_RECORDED': 'Payment recorded.',
    'SETTLEMENT_AMOUNT_EXCEEDS_BALANCE': 'Amount ({amount}) exceeds the outstanding balance ({balance}).',

    # Pack-to-unit selling / repackaging (C10)
    'PRODUCT_UNIT_NOT_FOUND': 'Sellable form not found.',
    'PRODUCT_UNIT_ROOT_NO_PARENT': 'The restock form cannot have a parent form.',
    'PRODUCT_UNIT_ROOT_NO_RATIO': 'The restock form cannot have a conversion ratio.',
    'PRODUCT_UNIT_ROOT_NOT_REPACKAGED': 'The restock form cannot be marked as a repackaging result.',
    'PRODUCT_UNIT_NEEDS_PARENT': 'This form needs a parent form to convert from.',
    'PRODUCT_UNIT_NEEDS_RATIO': 'Enter how many of this form make up one of its parent form.',
    'PRODUCT_UNIT_PARENT_WRONG_PRODUCT': 'The parent form must belong to the same product.',
    'PRODUCT_UNIT_ROOT_ALREADY_EXISTS': 'This product already has a restock form set up.',
    'PRODUCT_UNIT_CREATED': 'Sellable form added.',
    'PRODUCT_UNIT_UPDATED': 'Sellable form updated.',
    'PRODUCT_UNIT_DELETED': 'Sellable form removed.',
    'PRODUCT_UNIT_CANNOT_DELETE_HAS_CHILDREN': 'Remove the forms that convert from this one first.',
    'PRODUCT_UNIT_CANNOT_DELETE_ROOT': "The restock form can't be deleted — edit or delete the product instead.",
    'REPACKAGE_FROM_UNIT_NOT_FOUND': 'The form you are converting from was not found.',
    'REPACKAGE_TO_UNIT_NOT_FOUND': 'The form you are converting to was not found.',
    'REPACKAGE_DIFFERENT_PRODUCTS': 'Both forms must belong to the same product.',
    'REPACKAGE_TO_UNIT_NOT_REPACKAGED': 'That form is not set up as a repackaging result — check the product\'s units.',
    'REPACKAGE_WRONG_PARENT': 'You can only repackage into a direct child form of the one you are converting from.',
    'REPACKAGE_INSUFFICIENT_STOCK': "Not enough '{unit}' in stock. Available: {available}, requested: {requested}.",
    'REPACKAGE_RECORDED': 'Repackaging recorded.',
    'STOCK_MOVEMENT_REPACKAGE_OUT_NOTE': 'Repackaged into {to_unit}',
    'STOCK_MOVEMENT_REPACKAGE_IN_NOTE': 'Repackaged from {from_unit}',

    # Pack-to-unit selling — sale-flow integration (C10, sell config)
    'PRODUCT_UNIT_NOT_SELLABLE': 'This form is not available for sale.',
    'PRODUCT_UNIT_NO_SELLING_PRICE': "No selling price set for '{unit}' — add one on the product's units first.",
    'PRODUCT_UNIT_INSUFFICIENT_STOCK': "Not enough '{unit}' of '{name}' in stock. Remaining: {remaining}, requested: {requested}.",

    # Generic
    'SUCCESS': 'Operation completed successfully.',
    'ERROR': 'An error occurred. Please try again.',
    'SERVER_ERROR': 'Server error. Please contact support.',
    'VALIDATION_ERROR': 'Validation failed.',
    'CROSS_TENANT_FORBIDDEN': "You don't have permission to access another business's data.",
    'DEMO_EXPIRED': 'Your trial period has ended. Contact Lewis to subscribe.',
    'OWNER_ONLY': 'This action requires owner permission.',
    'OWNER_OR_MANAGER_ONLY': 'This action requires manager or owner permission.',
}

# Kiswahili translation corpus
MESSAGES_SW = {
    # Authentication & Authorization
    'INVALID_OTP': 'OTP si sahihi. Jaribu tena.',
    'OTP_EXPIRED': 'OTP imeipuka. Omba mpya.',
    'OTP_SENT': 'OTP imetumwa kwa {phone}.',
    'OTP_NOT_FOUND': 'OTP haikupatikana au imeisha muda wake.',
    'GOOGLE_SIGNIN_NOT_CONFIGURED': 'Kuingia na Google hakupatikani kwa sasa. Tafadhali tumia namba yako ya simu.',
    'GOOGLE_SIGNIN_INVALID_TOKEN': 'Imeshindwa kuthibitisha kuingia kwako na Google. Tafadhali jaribu tena.',
    'GOOGLE_SIGNIN_EMAIL_NOT_VERIFIED': 'Barua pepe yako ya Google haijathibitishwa. Tafadhali ithibitishe na Google kwanza.',
    'OTP_TOO_MANY_ATTEMPTS': 'Umejaribu mara nyingi. Omba OTP mpya.',
    'OTP_INVALID_WITH_ATTEMPTS': 'OTP si sahihi. Majaribio {remaining} yaliyobaki.',
    'LOGIN_FAILED': 'Imeshindwa kuingia. Hakiki taarifa zako.',
    'UNAUTHORIZED': 'Haina ruhusa ya kutekeleza kitendo hiki.',
    'INVALID_TOKEN': 'Token si sahihi au imeipuka.',
    'TOKEN_REFRESH_FAILED': 'Imeshindwa kubaharisha token. Ingia tena.',
    'REFRESH_TOKEN_NOT_FOUND': 'Refresh token haikupatikana.',
    'REFRESH_TOKEN_INVALID': 'Refresh token si sahihi au imeisha.',
    'TOKEN_REFRESHED': 'Token imefanywa upya.',
    'LOGGED_OUT': 'Umetoka kikao.',
    'DEV_BYPASS_MODE': 'Njia ya dev iko: tumia OTP 000000.',

    # Business
    'BUSINESS_NOT_FOUND': 'Biashara haikusumatwa.',
    'BUSINESS_NOT_REGISTERED': 'Biashara yako haijasajiliwa bado.',
    'BUSINESS_ALREADY_REGISTERED': 'Biashara yako tayari imesajiliwa.',
    'BUSINESS_NAME_REQUIRED': 'Jina la biashara linahitajika.',
    'INVALID_BUSINESS': 'Biashara si sahihi.',
    'BUSINESS_CREATED': 'Biashara imetengenezwa.',
    'BUSINESS_UPDATED': 'Biashara imebadilishwa.',

    # Staff & Invites
    'INVALID_ROLE': 'Nafasi si sahihi. Tumia CASHIER au MANAGER.',
    'TOKEN_AND_PHONE_REQUIRED': 'Kiungo cha mwaliko sahihi kinahitajika.',
    'FEATURE_NOT_IMPLEMENTED': 'Kipengele hiki kitakamilika na mfano wa StaffInvite.',
    'BUSINESS_NOT_FOUND_CREATE_FIRST': 'Biashara haijapatikana. Unda biashara kwanza.',
    'OWNER_PERMISSION_REQUIRED': 'Mabadiliko yanahitaji ruhusa ya mmiliki.',
    'STAFF_NOT_FOUND': 'Mfanyakazi haijapatikana.',
    'CANNOT_REMOVE_SELF': 'Huwezi kujiondoa mwenyewe.',
    'STAFF_REMOVED': 'Mfanyakazi ameondolewa.',
    'INVITE_INVALID': 'Kiungo hiki cha mwaliko si sahihi.',
    'INVITE_EXPIRED': 'Kiungo hiki cha mwaliko kimeisha muda. Mwombe mmiliki akutumie kingine.',
    'INVITE_ALREADY_USED': 'Kiungo hiki cha mwaliko kimeshatumika.',
    'INVITE_ACCEPTED': 'Umejiunga na biashara.',
    'USER_ALREADY_HAS_BUSINESS': 'Akaunti yako tayari imeunganishwa na biashara.',

    # Products & Catalog
    'PRODUCT_NOT_FOUND': 'Bidhaa haikusumatwa.',
    'PRODUCT_ALREADY_EXISTS': 'Bidhaa na SKU hii tayari ipo.',
    'INVALID_PRICE': 'Bei lazima iwe kubwa kuliko sifuri.',
    'INVALID_QUANTITY': 'Idadi lazima iwe kubwa kuliko sifuri.',
    'PRODUCT_CREATED': 'Bidhaa imetengenezwa.',
    'PRODUCT_UPDATED': 'Bidhaa imebadilishwa.',
    'PRODUCT_DELETED': 'Bidhaa imefutwa.',
    'PRODUCTS_NOT_FOUND': 'Hakuna bidhaa.',
    'CATEGORY_WRONG_BUSINESS': 'Kategoria hii si ya biashara yako.',

    # Shared product identity (barcode resolve/candidate/verify)
    'GLOBAL_PRODUCT_ALREADY_EXISTS': 'Bakodi hii tayari inajulikana. Jaribu kuiskani tena.',
    'GLOBAL_PRODUCT_NOT_FOUND': 'Hakuna bidhaa inayojulikana kwa bakodi hii.',
    'CSV_FILE_REQUIRED': 'Tuma faili ya CSV (key: "file").',
    'CSV_INVALID_FORMAT': 'Faili lazima iwe ya muundo .csv.',
    'CSV_FILE_TOO_LARGE': 'Faili kubwa mno. Kikomo ni {max_size}MB.',
    'STOCK_CANNOT_BE_NEGATIVE': 'Hisa haiwezi kuwa chini ya sifuri.',

    # Transactions
    'TRANSACTION_NOT_FOUND': 'Miamala haikusumatwa.',
    'RECEIPT_NOT_FOUND': 'Hakuna risiti yenye nambari hiyo. Hakiki umeandika sahihi.',
    'TRANSACTION_VOIDED': 'Miamala imebatilishwa.',
    'TRANSACTION_ALREADY_VOIDED': 'Muamala huu tayari umefutwa.',
    'REFUND_ORIGINAL_NOT_SALE': 'Ni muamala wa aina SALE tu unaoweza kurudishiwa.',
    'REFUND_ORIGINAL_VOIDED': 'Haiwezi kurudisha muamala uliobatilishwa.',
    'REFUND_ORIGINAL_NOT_CONFIRMED': 'Haiwezi kurudisha uzaji ambao malipo yake hayajathibitishwa.',
    'REFUND_AMOUNT_EXCEEDS_REMAINING': 'Haiwezi kurudisha KES {amount} — KES {remaining} tu ndio inayoweza kurudishwa kwenye uzaji huu.',
    'REFUND_PROCESSED': 'Kurudisha kumekamilika.',
    'INSUFFICIENT_STOCK': 'Hisa haitoshi kwa bidhaa hii.',
    'INSUFFICIENT_STOCK_DETAIL': "Hisa haitoshi kwa '{name}'. Iliyobaki: {remaining}, Ulioagiza: {requested}.",
    'PRODUCT_NOT_FOUND_WITH_ID': 'Bidhaa {product_id} haijapatikana.',
    'UNRECONCILED_GROUP_NOT_FOUND': 'Hakuna bidhaa za kawaida ambazo hazijatatuliwa na jina hilo — huenda tayari zimetatuliwa.',
    'MIXED_PAYMENT_AMOUNTS_MISMATCH': 'Kiasi cha taslimu, M-Pesa, na deni lazima jumla iwe sawa na jumla ya bei (KES {total}).',
    'CREDIT_CUSTOMER_REQUIRED': 'Ongeza jina la mteja ili kurekodi hii kama deni.',
    'CUSTOMER_NOT_FOUND': 'Mteja hakupatikana.',
    'ADJUSTMENT_NEGATIVE_STOCK': 'Mabadiliko yangesababisha hisa kuwa chini ya sifuri.',
    'DATA_HEALTH_REASON_COST_PRICE': 'Bidhaa {count} hazina bei ya ununuzi — ongeza ili kuona faida sahihi.',
    'DATA_HEALTH_REASON_TAXONOMY_DEPTH': 'Asilimia {percentage}% pekee ya bidhaa zako zina maelezo ya chapa (mfano "Jameson" badala ya "Whisky").',
    'DATA_HEALTH_REASON_RECONCILIATION': 'Bidhaa {count} za mauzo bado zinahitaji kuunganishwa na bidhaa halisi kwenye Hisa.',
    'MILESTONE_HIGHEST_DAY_SALES': 'Siku bora zaidi — KES {value} katika mauzo.',
    'MILESTONE_FULLY_RECONCILED_WEEK': 'Wiki nzima ambapo kila bidhaa ya mauzo imeunganishwa na bidhaa halisi.',
    'MILESTONE_CONFIDENCE_TO_ACT': "Ripoti yako ya faida sasa ni sahihi kikamilifu — asilimia {percentage}% ya bidhaa zako zina bei ya ununuzi.",
    'STOCK_MOVEMENT_REFUND_NOTE': 'Kurudisha: {reference}',
    'SALE_CREATED': 'Uza umerekodiwa.',
    'SALE_VOIDED': 'Uza umebatilishwa.',
    'INVALID_PAYMENT_METHOD': 'Njia ya malipo si sahihi.',
    'PAYMENT_PENDING': 'Malipo yanasubiri.',
    'PAYMENT_CONFIRMED': 'Malipo yamethibitishwa.',
    'PAYMENT_FAILED': 'Malipo hayajafaulu. Jaribu tena.',
    'TRANSACTION_CREATED': 'Miamala imetengenezwa.',

    # Stock & Inventory
    'STOCK_IN_RECORDED': 'Hisa imepokelewa na kurekodi.',
    'STOCK_LOSS_RECORDED': 'Hasara ya hisa imerekodiwa.',
    'STOCK_COUNT_SUBMITTED': 'Hesabu ya hisa imewasilishwa.',
    'STOCK_COUNT_NOTE': 'Hesabu ya mwili: {quantity}',
    'LOW_STOCK_THRESHOLD_SET': 'Kiwango cha chini cha hisa kimebadilishwa.',
    'STOCK_UPDATED': 'Hisa imebadilishwa.',

    # Payments & M-Pesa
    'PAYMENT_NOT_FOUND': 'Malipo hayapatikani.',
    'STK_PUSH_SENT': 'Mwaliko wa malipo imetumwa kwa simu.',
    'STK_PUSH_FAILED': 'Imeshindwa kutuma mwaliko wa malipo. Jaribu tena.',
    'C2B_REGISTRATION_FAILED': 'Usajili wa C2B umeshindwa.',
    'CALLBACK_PROCESSED': 'Callback imepokelewa.',
    'TRANSACTION_NOT_MPESA': 'Muamala huu si wa malipo ya M-Pesa.',
    'TRANSACTION_ALREADY_PROCESSED': 'Muamala huu tayari umeshughulikiwa.',
    'STK_REQUEST_ALREADY_PENDING': 'Ombi la STK Push tayari linasubiriwa kwa muamala huu.',
    'STK_REQUEST_NOT_FOUND': 'Ombi halijapatikana.',
    'MPESA_TRANSACTION_NOT_FOUND': 'Muamala wa M-Pesa haujapatikana.',

    # Subscription billing (company M-Pesa, not a business sale)
    'SUBSCRIPTION_PAYMENT_SENT': 'Mwaliko wa malipo imetumwa kwa simu.',
    'SUBSCRIPTION_PAYMENT_FAILED': 'Imeshindwa kutuma mwaliko wa malipo. Jaribu tena.',
    'SUBSCRIPTION_PAYMENT_ALREADY_PENDING': 'Ombi la malipo ya usajili tayari linasubiriwa.',
    'SUBSCRIPTION_PAYMENT_NOT_FOUND': 'Malipo ya usajili hayajapatikana.',
    'SUBSCRIPTION_PAYMENT_CONFIRMED': 'Malipo ya usajili yamethibitishwa.',

    # Business M-Pesa credentials (per-business Daraja app)
    'MPESA_CREDENTIALS_SAVED': 'Mipangilio ya M-Pesa imehifadhiwa.',
    'MPESA_CREDENTIALS_NOT_CONFIGURED': 'Taarifa za M-Pesa hazijajazwa kikamilifu bado.',
    'MPESA_CREDENTIALS_VERIFIED': 'Taarifa za M-Pesa zimehakikiwa na kuwashwa.',
    'MPESA_CREDENTIALS_VERIFY_FAILED': 'Imeshindikana kuhakiki taarifa hizi za M-Pesa. Tafadhali zikague na ujaribu tena.',
    'MPESA_CREDENTIALS_DEACTIVATED': 'Nambari yako ya M-Pesa imezimwa — mauzo yatatumia nambari ya pamoja ya BizYangu tena.',

    # Notifications & Push
    'DEVICE_REGISTERED': 'Simu imesajiliwa kwa arifa.',
    'DEVICE_UNREGISTERED': 'Simu imeondolewa kwa arifa.',
    'NOTIFICATION_SENT': 'Arifa imetumwa.',
    'TOKEN_REQUIRED': 'Token inahitajika.',
    'OUT_OF_STOCK_TITLE': 'Bidhaa Imeisha',
    'LOW_STOCK_TITLE': 'Bidhaa Inakaribia Kuisha',
    'OUT_OF_STOCK_BODY': '{product} imeisha kabisa. Ongeza stoki haraka.',
    'LOW_STOCK_BODY': '{product} ina {stock} {unit} pekee — chini ya kiwango cha {threshold}.',

    # Reports
    'REPORT_GENERATED': 'Ripoti imetengenezwa.',
    'REPORT_NOT_FOUND': 'Ripoti haikusumatwa.',
    'INVALID_DATE_FORMAT': 'Tarehe si sahihi. Tumia muundo YYYY-MM-DD.',
    'INVALID_DATE_RANGE': 'Tarehe ya kuanza lazima iwe kabla au sawa na tarehe ya mwisho.',
    'DATE_RANGE_TOO_LARGE': 'Muda hauwezi kuzidi siku {max_days}.',

    # Validation Errors
    'REQUIRED_FIELD': 'Uga hili linahitajika.',
    'INVALID_FORMAT': 'Umbizo si sahihi.',
    'DUPLICATE_ENTRY': 'Ingizo hili tayari lipo.',
    'NOT_FOUND': 'Haikusumatwa.',
    'INVALID_PHONE_NUMBER': 'Namba ya simu si sahihi.',
    'INVALID_PHONE_NUMBER_FORMAT': 'Nambari ya simu si sahihi. Tumia muundo: +254XXXXXXXXX au 07XXXXXXXX',
    'FIRST_NAME_REQUIRED': 'Jina la kwanza linahitajika.',
    'LAST_NAME_REQUIRED': 'Jina la mwisho linahitajika.',
    'EMAIL_ALREADY_IN_USE': 'Barua pepe hiyo tayari inatumiwa na akaunti nyingine.',
    'INVALID_EMAIL_FORMAT': 'Tafadhali weka barua pepe sahihi.',
    'ACCOUNT_UPDATED': 'Maelezo ya akaunti yamesasishwa.',

    # Customers & Credit (Phase 12)
    'CUSTOMER_PHONE_IN_USE': 'Mteja mwenye namba hii ya simu tayari yupo.',
    'SETTLEMENT_RECORDED': 'Malipo yamerekodiwa.',
    'SETTLEMENT_AMOUNT_EXCEEDS_BALANCE': 'Kiasi ({amount}) kimezidi deni lililobaki ({balance}).',

    # Pack-to-unit selling / repackaging (C10)
    'PRODUCT_UNIT_NOT_FOUND': 'Aina ya kuuza haikupatikana.',
    'PRODUCT_UNIT_ROOT_NO_PARENT': 'Aina ya kuongeza stoo haiwezi kuwa na aina mzazi.',
    'PRODUCT_UNIT_ROOT_NO_RATIO': 'Aina ya kuongeza stoo haiwezi kuwa na uwiano wa ubadilishaji.',
    'PRODUCT_UNIT_ROOT_NOT_REPACKAGED': 'Aina ya kuongeza stoo haiwezi kuwekwa alama kama matokeo ya ufungashaji upya.',
    'PRODUCT_UNIT_NEEDS_PARENT': 'Aina hii inahitaji aina mzazi ya kubadilisha kutoka.',
    'PRODUCT_UNIT_NEEDS_RATIO': 'Weka ni ngapi za aina hii zinazounda moja ya aina mzazi.',
    'PRODUCT_UNIT_PARENT_WRONG_PRODUCT': 'Aina mzazi lazima iwe ya bidhaa ile ile.',
    'PRODUCT_UNIT_ROOT_ALREADY_EXISTS': 'Bidhaa hii tayari ina aina ya kuongeza stoo iliyowekwa.',
    'PRODUCT_UNIT_CREATED': 'Aina ya kuuza imeongezwa.',
    'PRODUCT_UNIT_UPDATED': 'Aina ya kuuza imesasishwa.',
    'PRODUCT_UNIT_DELETED': 'Aina ya kuuza imeondolewa.',
    'PRODUCT_UNIT_CANNOT_DELETE_HAS_CHILDREN': 'Ondoa kwanza aina zinazobadilishwa kutoka kwa hii.',
    'PRODUCT_UNIT_CANNOT_DELETE_ROOT': 'Aina ya kuongeza stoo haiwezi kufutwa — hariri au futa bidhaa badala yake.',
    'REPACKAGE_FROM_UNIT_NOT_FOUND': 'Aina unayobadilisha kutoka haikupatikana.',
    'REPACKAGE_TO_UNIT_NOT_FOUND': 'Aina unayobadilisha kwenda haikupatikana.',
    'REPACKAGE_DIFFERENT_PRODUCTS': 'Aina zote mbili lazima ziwe za bidhaa ile ile.',
    'REPACKAGE_TO_UNIT_NOT_REPACKAGED': 'Aina hiyo haijawekwa kama matokeo ya ufungashaji upya — angalia aina za bidhaa.',
    'REPACKAGE_WRONG_PARENT': 'Unaweza tu kufungasha upya kwenda aina mtoto wa moja kwa moja ya ile unayobadilisha kutoka.',
    'REPACKAGE_INSUFFICIENT_STOCK': "Hisa ya '{unit}' haitoshi. Iliyopo: {available}, Uliyoomba: {requested}.",
    'REPACKAGE_RECORDED': 'Ufungashaji upya umerekodiwa.',
    'STOCK_MOVEMENT_REPACKAGE_OUT_NOTE': 'Imefungashwa upya kuwa {to_unit}',
    'STOCK_MOVEMENT_REPACKAGE_IN_NOTE': 'Imefungashwa upya kutoka {from_unit}',

    # Pack-to-unit selling — sale-flow integration (C10, sell config)
    'PRODUCT_UNIT_NOT_SELLABLE': 'Aina hii haipatikani kwa kuuza.',
    'PRODUCT_UNIT_NO_SELLING_PRICE': "Hakuna bei ya kuuza iliyowekwa kwa '{unit}' — weka bei kwenye aina za bidhaa kwanza.",
    'PRODUCT_UNIT_INSUFFICIENT_STOCK': "Hisa ya '{unit}' ya '{name}' haitoshi. Iliyobaki: {remaining}, Ulioomba: {requested}.",

    # Generic
    'SUCCESS': 'Kitendo kimefaulu.',
    'ERROR': 'Kosa limetokea. Jaribu tena.',
    'SERVER_ERROR': 'Kosa la seva. Wasiliana na msaada.',
    'VALIDATION_ERROR': 'Uthibitisho umeshindwa.',
    'CROSS_TENANT_FORBIDDEN': 'Huna ruhusa ya kufikia data ya biashara nyingine.',
    'DEMO_EXPIRED': 'Kipindi chako cha majaribio kimeisha. Wasiliana na Lewis kupata usajili.',
    'OWNER_ONLY': 'Kitendo hiki kinahitaji ruhusa ya mmiliki.',
    'OWNER_OR_MANAGER_ONLY': 'Kitendo hiki kinahitaji ruhusa ya msimamizi au mmiliki.',
}