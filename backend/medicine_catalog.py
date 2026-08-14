"""Seed catalog used by prescription and pharmacy dropdowns.

Names include strength/form so a selection is unambiguous while the prescribed
dosage, frequency, and duration remain clinician-entered fields.
"""

_GROUPS = {
    "Pain & fever": [
        "Paracetamol 500 mg Tablet", "Paracetamol 650 mg Tablet",
        "Paracetamol 250 mg/5 mL Suspension", "Ibuprofen 200 mg Tablet",
        "Ibuprofen 400 mg Tablet", "Ibuprofen 100 mg/5 mL Suspension",
        "Diclofenac 50 mg Tablet", "Diclofenac 1% Topical Gel",
        "Naproxen 250 mg Tablet", "Naproxen 500 mg Tablet",
        "Aceclofenac 100 mg Tablet", "Aspirin 75 mg Tablet",
    ],
    "Antibiotics": [
        "Amoxicillin 250 mg Capsule", "Amoxicillin 500 mg Capsule",
        "Amoxicillin + Clavulanate 625 mg Tablet",
        "Amoxicillin + Clavulanate 457 mg/5 mL Suspension",
        "Azithromycin 250 mg Tablet", "Azithromycin 500 mg Tablet",
        "Cefixime 200 mg Tablet", "Cefuroxime 500 mg Tablet",
        "Cephalexin 500 mg Capsule", "Doxycycline 100 mg Capsule",
        "Ciprofloxacin 500 mg Tablet", "Levofloxacin 500 mg Tablet",
        "Metronidazole 400 mg Tablet", "Clindamycin 300 mg Capsule",
        "Nitrofurantoin 100 mg Capsule", "Fosfomycin 3 g Sachet",
    ],
    "Allergy & cold": [
        "Cetirizine 10 mg Tablet", "Levocetirizine 5 mg Tablet",
        "Loratadine 10 mg Tablet", "Fexofenadine 120 mg Tablet",
        "Fexofenadine 180 mg Tablet", "Chlorpheniramine 4 mg Tablet",
        "Montelukast 10 mg Tablet", "Montelukast + Levocetirizine Tablet",
        "Phenylephrine 10 mg Tablet", "Xylometazoline 0.1% Nasal Drops",
        "Saline 0.65% Nasal Spray", "Dextromethorphan 15 mg/5 mL Syrup",
    ],
    "Respiratory": [
        "Salbutamol 100 mcg Inhaler", "Salbutamol 2 mg/5 mL Syrup",
        "Budesonide 200 mcg Inhaler", "Budesonide 0.5 mg Nebulizer Respules",
        "Formoterol + Budesonide 6/200 mcg Inhaler",
        "Tiotropium 18 mcg Inhalation Capsule", "Ipratropium 20 mcg Inhaler",
        "Levosalbutamol 50 mcg Inhaler", "Theophylline 200 mg Tablet",
        "Acetylcysteine 600 mg Effervescent Tablet",
    ],
    "Gastrointestinal": [
        "Pantoprazole 40 mg Tablet", "Omeprazole 20 mg Capsule",
        "Rabeprazole 20 mg Tablet", "Esomeprazole 40 mg Tablet",
        "Famotidine 20 mg Tablet", "Domperidone 10 mg Tablet",
        "Ondansetron 4 mg Tablet", "Ondansetron 4 mg/2 mL Injection",
        "Metoclopramide 10 mg Tablet", "Sucralfate 1 g Tablet",
        "Lactulose 10 g/15 mL Solution", "Bisacodyl 5 mg Tablet",
        "Loperamide 2 mg Capsule", "ORS Oral Rehydration Salts Sachet",
        "Simethicone 80 mg Chewable Tablet",
    ],
    "Diabetes": [
        "Metformin 500 mg Tablet", "Metformin 850 mg Tablet",
        "Metformin XR 500 mg Tablet", "Glimepiride 1 mg Tablet",
        "Glimepiride 2 mg Tablet", "Gliclazide MR 60 mg Tablet",
        "Sitagliptin 100 mg Tablet", "Vildagliptin 50 mg Tablet",
        "Empagliflozin 10 mg Tablet", "Dapagliflozin 10 mg Tablet",
        "Human Regular Insulin 100 IU/mL", "Insulin Glargine 100 IU/mL",
    ],
    "Blood pressure & heart": [
        "Amlodipine 5 mg Tablet", "Amlodipine 10 mg Tablet",
        "Telmisartan 40 mg Tablet", "Telmisartan 80 mg Tablet",
        "Losartan 50 mg Tablet", "Olmesartan 20 mg Tablet",
        "Enalapril 5 mg Tablet", "Ramipril 5 mg Capsule",
        "Atenolol 50 mg Tablet", "Metoprolol XL 50 mg Tablet",
        "Carvedilol 6.25 mg Tablet", "Hydrochlorothiazide 12.5 mg Tablet",
        "Furosemide 40 mg Tablet", "Spironolactone 25 mg Tablet",
        "Clopidogrel 75 mg Tablet", "Atorvastatin 10 mg Tablet",
        "Atorvastatin 20 mg Tablet", "Rosuvastatin 10 mg Tablet",
        "Nitroglycerin 0.5 mg Sublingual Tablet",
    ],
    "Neurology & mental health": [
        "Gabapentin 300 mg Capsule", "Pregabalin 75 mg Capsule",
        "Carbamazepine 200 mg Tablet", "Sodium Valproate 500 mg Tablet",
        "Levetiracetam 500 mg Tablet", "Topiramate 25 mg Tablet",
        "Amitriptyline 10 mg Tablet", "Escitalopram 10 mg Tablet",
        "Sertraline 50 mg Tablet", "Fluoxetine 20 mg Capsule",
        "Duloxetine 30 mg Capsule", "Clonazepam 0.5 mg Tablet",
        "Donepezil 5 mg Tablet", "Betahistine 16 mg Tablet",
    ],
    "Thyroid & hormones": [
        "Levothyroxine 25 mcg Tablet", "Levothyroxine 50 mcg Tablet",
        "Levothyroxine 75 mcg Tablet", "Levothyroxine 100 mcg Tablet",
        "Carbimazole 5 mg Tablet", "Prednisolone 5 mg Tablet",
        "Prednisolone 10 mg Tablet", "Hydrocortisone 10 mg Tablet",
        "Medroxyprogesterone 10 mg Tablet", "Progesterone 200 mg Capsule",
    ],
    "Vitamins & minerals": [
        "Calcium Carbonate 500 mg Tablet", "Calcium + Vitamin D3 Tablet",
        "Cholecalciferol 60,000 IU Capsule", "Vitamin B Complex Tablet",
        "Methylcobalamin 1500 mcg Tablet", "Folic Acid 5 mg Tablet",
        "Ferrous Ascorbate + Folic Acid Tablet", "Zinc 20 mg Tablet",
        "Magnesium Oxide 400 mg Tablet", "Multivitamin Tablet",
    ],
    "Skin": [
        "Clotrimazole 1% Cream", "Miconazole 2% Cream",
        "Terbinafine 1% Cream", "Ketoconazole 2% Cream",
        "Hydrocortisone 1% Cream", "Calamine Lotion",
        "Mupirocin 2% Ointment", "Fusidic Acid 2% Cream",
        "Adapalene 0.1% Gel", "Benzoyl Peroxide 2.5% Gel",
        "Permethrin 5% Cream", "Moisturizing Cream 100 g",
    ],
    "Eye & ear": [
        "Carboxymethylcellulose 0.5% Eye Drops", "Moxifloxacin 0.5% Eye Drops",
        "Tobramycin 0.3% Eye Drops", "Olopatadine 0.1% Eye Drops",
        "Timolol 0.5% Eye Drops", "Latanoprost 0.005% Eye Drops",
        "Ciprofloxacin 0.3% Ear Drops", "Clotrimazole 1% Ear Drops",
    ],
    "Women's health": [
        "Tranexamic Acid 500 mg Tablet", "Mefenamic Acid 500 mg Tablet",
        "Clomiphene 50 mg Tablet", "Ethinylestradiol + Levonorgestrel Tablet",
        "Levonorgestrel 1.5 mg Tablet", "Iron + Folic Acid Tablet",
        "Calcium 500 mg + Vitamin D3 Tablet", "Doxylamine + Pyridoxine Tablet",
    ],
    "Urology & kidney": [
        "Tamsulosin 0.4 mg Capsule", "Finasteride 5 mg Tablet",
        "Potassium Citrate 10 mEq Tablet", "Potassium Citrate Oral Solution",
        "Allopurinol 100 mg Tablet", "Febuxostat 40 mg Tablet",
        "Solifenacin 5 mg Tablet", "Sodium Bicarbonate 500 mg Tablet",
    ],
    "Antifungal & antiviral": [
        "Fluconazole 150 mg Tablet", "Itraconazole 100 mg Capsule",
        "Acyclovir 400 mg Tablet", "Valacyclovir 500 mg Tablet",
        "Oseltamivir 75 mg Capsule", "Albendazole 400 mg Tablet",
        "Ivermectin 6 mg Tablet", "Nystatin 100,000 IU/mL Oral Suspension",
    ],
    "Emergency & supportive": [
        "Adrenaline 1 mg/mL Injection", "Atropine 0.6 mg/mL Injection",
        "Dextrose 25% Injection", "Normal Saline 0.9% 500 mL",
        "Ringer Lactate 500 mL", "Dextrose 5% 500 mL",
        "Lidocaine 2% Injection", "Activated Charcoal 50 g Suspension",
    ],
}

MEDICINE_CATALOG = [
    (name, category)
    for category, names in _GROUPS.items()
    for name in names
]
