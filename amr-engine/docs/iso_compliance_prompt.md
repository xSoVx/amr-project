# Claude Fix Prompt: ISO 13485 & ISO 14971 Medical Device Compliance

## 🎯 **Objective**
Implement comprehensive medical device compliance for the AMR Classification Engine according to ISO 13485 (Quality Management Systems) and ISO 14971 (Risk Management) standards.

## 📋 **Requirements**

### **ISO 13485 Implementation Requirements:**

1. **Quality Management System (QMS) Framework**
   - Document control procedures
   - Management responsibility structure  
   - Resource management processes
   - Product realization controls
   - Measurement and improvement processes

2. **Design Controls (Section 7.3)**
   - Design and development planning
   - Design inputs documentation
   - Design outputs specification
   - Design review processes
   - Design verification procedures
   - Design validation protocols
   - Design transfer documentation
   - Design changes control

3. **Software Lifecycle Processes (IEC 62304)**
   - Software safety classification (Class B - Non-Life-Threatening)
   - Software development lifecycle documentation
   - Software verification and validation
   - Software configuration management
   - Software problem resolution

### **ISO 14971 Risk Management Requirements:**

1. **Risk Management Process**
   - Risk analysis methodology
   - Risk evaluation criteria
   - Risk control measures
   - Residual risk evaluation
   - Risk management file documentation

2. **AMR-Specific Risk Identification**
   - Clinical decision impact risks
   - Data integrity risks
   - System availability risks
   - User interface risks
   - Integration risks with healthcare systems

## 🔧 **Implementation Tasks**

### **Task 1: QMS Framework Setup**

```yaml
# File: quality_management/qms_config.yaml
medical_device_classification:
  device_class: "Class IIa" 
  software_safety_class: "Class B"
  intended_use: "Clinical decision support for antimicrobial resistance classification"
  regulatory_pathway: "FDA 510(k) / EU MDR"

quality_processes:
  document_control:
    procedure: "QP-001 Document Control"
    responsibility: "Quality Manager"
    review_cycle: "Annual"
  
  design_controls:
    procedure: "QP-002 Design Controls"
    phases: ["Planning", "Inputs", "Outputs", "Review", "Verification", "Validation", "Transfer"]
    
  risk_management:
    procedure: "QP-003 Risk Management" 
    standard: "ISO 14971:2019"
    review_frequency: "Quarterly"
```

**Implementation Instructions:**
1. Create QMS documentation structure following ISO 13485 sections
2. Establish design control procedures with defined gates and reviews
3. Implement software lifecycle processes per IEC 62304
4. Set up management review processes for continual improvement

### **Task 2: Risk Management Implementation**

```python
# File: medical_device/risk_management_system.py

class AMRRiskManagementSystem:
    """Complete ISO 14971 Risk Management Implementation"""
    
    def __init__(self):
        self.risk_management_file = RiskManagementFile()
        self.hazard_analysis = HazardAnalysis()
        self.risk_controls = RiskControlManager()
        
    async def comprehensive_risk_analysis(self):
        """Perform systematic risk analysis per ISO 14971"""
        
        # Step 1: Intended use and characteristics analysis
        device_characteristics = {
            "intended_use": "AMR classification for clinical decision support",
            "user_profile": "Healthcare professionals, laboratory technicians",
            "use_environment": "Hospital laboratories, clinical settings",
            "operational_principle": "Algorithm-based antimicrobial susceptibility interpretation"
        }
        
        # Step 2: Identify known and foreseeable hazards
        hazards = await self._identify_comprehensive_hazards()
        
        # Step 3: Estimate risks for each hazardous situation
        risk_estimates = await self._estimate_risks(hazards)
        
        # Step 4: Evaluate risk acceptability
        risk_evaluation = await self._evaluate_risk_acceptability(risk_estimates)
        
        # Step 5: Risk control measures
        control_measures = await self._implement_risk_controls(risk_evaluation)
        
        # Step 6: Evaluate residual risk
        residual_risks = await self._evaluate_residual_risks(control_measures)
        
        # Step 7: Risk/benefit analysis
        risk_benefit = await self._perform_risk_benefit_analysis(residual_risks)
        
        return {
            "device_characteristics": device_characteristics,
            "hazard_analysis": hazards,
            "risk_estimates": risk_estimates,
            "control_measures": control_measures,
            "residual_risks": residual_risks,
            "risk_benefit_analysis": risk_benefit
        }
        
    async def _identify_comprehensive_hazards(self):
        """Comprehensive hazard identification for AMR systems"""
        return [
            # Clinical Decision Hazards
            {
                "hazard_id": "H-CD-001",
                "category": "Clinical Decision",
                "hazard": "Incorrect susceptibility classification",
                "sequence": "Algorithm error → Wrong S/I/R result → Inappropriate therapy",
                "harm": "Treatment failure, increased morbidity/mortality",
                "severity": 4,  # Critical
                "probability": 2,  # Remote
                "risk_level": 8
            },
            # Data Integrity Hazards  
            {
                "hazard_id": "H-DI-001",
                "category": "Data Integrity",
                "hazard": "Corrupted input data",
                "sequence": "Data corruption → Invalid classification → Clinical error",
                "harm": "Incorrect treatment decisions",
                "severity": 3,  # Serious
                "probability": 2,  # Remote
                "risk_level": 6
            },
            # System Availability Hazards
            {
                "hazard_id": "H-SA-001", 
                "category": "System Availability",
                "hazard": "System downtime during critical period",
                "sequence": "System failure → Delayed diagnosis → Treatment delay",
                "harm": "Delayed appropriate therapy",
                "severity": 3,  # Serious
                "probability": 3,  # Occasional
                "risk_level": 9
            },
            # User Interface Hazards
            {
                "hazard_id": "H-UI-001",
                "category": "User Interface", 
                "hazard": "Confusing or ambiguous results display",
                "sequence": "Poor UI → Misinterpretation → Wrong clinical decision",
                "harm": "Inappropriate antimicrobial selection",
                "severity": 3,  # Serious
                "probability": 2,  # Remote  
                "risk_level": 6
            },
            # Cybersecurity Hazards
            {
                "hazard_id": "H-CS-001",
                "category": "Cybersecurity",
                "hazard": "Unauthorized system access",
                "sequence": "Security breach → Data manipulation → False results",
                "harm": "Compromised patient safety and privacy",
                "severity": 4,  # Critical
                "probability": 2,  # Remote
                "risk_level": 8
            }
        ]
```

### **Task 3: Clinical Evaluation Framework**

```python
# File: medical_device/clinical_evaluation.py

class ClinicalEvaluationPlan:
    """ISO 13485 Clinical Evaluation Implementation"""
    
    def __init__(self):
        self.evaluation_protocol = self._create_evaluation_protocol()
        
    def _create_evaluation_protocol(self):
        return {
            "study_design": "Prospective observational study",
            "primary_endpoint": "Concordance with reference laboratory methods ≥95%",
            "secondary_endpoints": [
                "Clinical impact on antimicrobial selection",
                "Time to appropriate therapy",
                "User satisfaction and workflow integration",
                "Safety profile assessment"
            ],
            "sample_size": {
                "target": 1000,
                "rationale": "Powered to detect 95% concordance with 95% confidence",
                "organism_distribution": "Representative of clinical isolates"
            },
            "statistical_plan": {
                "primary_analysis": "Concordance rate with 95% CI",
                "secondary_analyses": "Subrungroup analyses by organism/antibiotic",
                "safety_analysis": "Descriptive analysis of adverse events"
            }
        }
        
    async def conduct_literature_review(self):
        """Systematic literature review per ISO 13485"""
        return {
            "search_strategy": "Comprehensive search of AMR classification systems",
            "inclusion_criteria": [
                "Peer-reviewed publications",
                "AMR classification algorithms", 
                "Clinical validation studies",
                "Safety and performance data"
            ],
            "data_extraction": [
                "Study design and methodology",
                "Performance characteristics",
                "Clinical outcomes",
                "Safety profile"
            ],
            "quality_assessment": "Critical appraisal using established tools"
        }
```

### **Task 4: Software Verification & Validation**

```python
# File: medical_device/software_validation.py

class SoftwareValidationFramework:
    """IEC 62304 Software Lifecycle Processes"""
    
    def __init__(self):
        self.safety_class = "Class B"  # Non-life-threatening
        self.validation_plan = self._create_validation_plan()
        
    def _create_validation_plan(self):
        return {
            "verification_activities": [
                "Unit testing (≥90% code coverage)",
                "Integration testing",
                "System testing",
                "Performance testing",
                "Security testing",
                "Usability testing"
            ],
            "validation_activities": [
                "Clinical algorithm validation",
                "User needs validation", 
                "Intended use validation",
                "Clinical environment validation"
            ],
            "test_environments": [
                "Development environment",
                "Staging environment", 
                "Clinical simulation environment",
                "Production environment"
            ]
        }
        
    async def execute_verification_protocol(self):
        """Execute software verification per IEC 62304"""
        verification_results = {
            "requirements_traceability": await self._verify_requirements_traceability(),
            "algorithm_accuracy": await self._verify_algorithm_accuracy(),
            "performance_testing": await self._verify_performance_requirements(),
            "security_testing": await self._verify_security_requirements(),
            "usability_testing": await self._verify_usability_requirements()
        }
        return verification_results
        
    async def execute_validation_protocol(self):
        """Execute software validation per IEC 62304"""
        validation_results = {
            "clinical_validation": await self._validate_clinical_performance(),
            "user_validation": await self._validate_user_workflows(),
            "environment_validation": await self._validate_clinical_environment()
        }
        return validation_results
```

### **Task 5: Post-Market Surveillance**

```python
# File: medical_device/post_market_surveillance.py

class PostMarketSurveillanceSystem:
    """ISO 13485 Post-Market Surveillance Implementation"""
    
    def __init__(self):
        self.surveillance_plan = self._create_surveillance_plan()
        
    def _create_surveillance_plan(self):
        return {
            "monitoring_activities": [
                "Adverse event reporting and investigation",
                "Performance trend analysis",
                "User feedback collection and analysis", 
                "Software update impact assessment",
                "Comparative performance studies"
            ],
            "data_sources": [
                "Clinical incident reports",
                "User feedback systems",
                "Performance monitoring dashboards",
                "Literature surveillance",
                "Regulatory communications"
            ],
            "review_frequency": {
                "safety_data": "Weekly",
                "performance_data": "Monthly", 
                "trend_analysis": "Quarterly",
                "comprehensive_review": "Annually"
            }
        }
        
    async def monitor_safety_performance(self):
        """Continuous safety and performance monitoring"""
        monitoring_results = {
            "safety_signals": await self._detect_safety_signals(),
            "performance_trends": await self._analyze_performance_trends(),
            "user_satisfaction": await self._track_user_satisfaction(),
            "clinical_outcomes": await self._monitor_clinical_outcomes()
        }
        return monitoring_results
```

## 📝 **Documentation Requirements**

### **Required Documentation Deliverables:**

1. **Design History File (DHF)**
   - Design inputs and outputs
   - Design review records
   - Verification and validation protocols and reports
   - Design transfer documentation
   - Design change control records

2. **Risk Management File (RMF)**
   - Risk analysis documentation
   - Risk evaluation records
   - Risk control implementation
   - Residual risk assessment
   - Risk-benefit analysis
   - Post-production risk monitoring

3. **Software File**
   - Software development plan
   - Software requirements specification
   - Software architecture documentation
   - Software verification and validation
   - Configuration management records

4. **Clinical Evaluation Report**
   - Literature review results
   - Clinical data analysis
   - Clinical performance assessment
   - Safety profile evaluation
   - Benefit-risk determination

5. **Technical Documentation**
   - Software user manual
   - Installation and maintenance procedures
   - Cybersecurity documentation
   - Interoperability specifications

### **Task 6: Documentation Framework Implementation**

```python
# File: medical_device/documentation_manager.py

class MedicalDeviceDocumentationManager:
    """Manage all ISO 13485 required documentation"""
    
    def __init__(self):
        self.document_control = DocumentControlSystem()
        self.dhf = DesignHistoryFile()
        self.rmf = RiskManagementFile() 
        self.clinical_file = ClinicalEvaluationFile()
        
    async def generate_design_history_file(self):
        """Generate complete Design History File"""
        dhf_contents = {
            "design_inputs": {
                "user_needs": await self._document_user_needs(),
                "intended_use": await self._document_intended_use(),
                "functional_requirements": await self._document_functional_requirements(),
                "performance_requirements": await self._document_performance_requirements(),
                "safety_requirements": await self._document_safety_requirements(),
                "regulatory_requirements": await self._document_regulatory_requirements()
            },
            "design_outputs": {
                "software_specifications": await self._document_software_specs(),
                "user_interface_design": await self._document_ui_design(),
                "system_architecture": await self._document_architecture(),
                "algorithm_specifications": await self._document_algorithms(),
                "test_specifications": await self._document_test_specs()
            },
            "design_reviews": {
                "review_1_planning": await self._document_design_review_1(),
                "review_2_inputs": await self._document_design_review_2(),
                "review_3_outputs": await self._document_design_review_3(),
                "review_4_verification": await self._document_design_review_4(),
                "review_5_validation": await self._document_design_review_5(),
                "review_6_transfer": await self._document_design_review_6()
            },
            "verification_validation": {
                "verification_protocols": await self._document_verification_protocols(),
                "verification_reports": await self._document_verification_reports(),
                "validation_protocols": await self._document_validation_protocols(),
                "validation_reports": await self._document_validation_reports()
            },
            "design_transfer": {
                "transfer_plan": await self._document_transfer_plan(),
                "production_procedures": await self._document_production_procedures(),
                "acceptance_criteria": await self._document_acceptance_criteria(),
                "transfer_review": await self._document_transfer_review()
            }
        }
        
        return dhf_contents
        
    async def _document_user_needs(self):
        """Document user needs per ISO 13485 7.3.3"""
        return {
            "clinical_users": [
                "Rapid and accurate AMR classification",
                "Integration with laboratory workflows", 
                "Clear and intuitive result presentation",
                "Reliable system availability",
                "Comprehensive audit capabilities"
            ],
            "technical_users": [
                "Easy system deployment and maintenance",
                "Scalable architecture for growth",
                "Comprehensive monitoring and alerting",
                "Secure data handling and transmission",
                "Standards-compliant interfaces"
            ],
            "regulatory_needs": [
                "HIPAA compliance for PHI protection",
                "FHIR R4 interoperability standards",
                "FDA/EU MDR regulatory requirements",
                "Audit trail capabilities",
                "Change control procedures"
            ]
        }
        
    async def _document_safety_requirements(self):
        """Document safety requirements from risk analysis"""
        return {
            "patient_safety": [
                "Algorithm accuracy ≥95% concordance with reference methods",
                "Clear indication of system limitations",
                "Fail-safe mechanisms for invalid inputs",
                "Comprehensive error handling and user notifications",
                "Backup and recovery procedures"
            ],
            "data_safety": [
                "End-to-end encryption of PHI",
                "Access controls and authentication",
                "Audit logging of all data access",
                "Data integrity verification",
                "Secure data transmission protocols"
            ],
            "operational_safety": [
                "High availability (≥99.5% uptime)",
                "Performance monitoring and alerting",
                "Graceful degradation during failures",
                "User training and competency requirements",
                "Change control procedures"
            ]
        }
```

### **Task 7: Regulatory Submission Preparation**

```python
# File: medical_device/regulatory_submission.py

class RegulatorySubmissionManager:
    """Manage regulatory submissions for medical device approval"""
    
    def __init__(self):
        self.submission_type = "FDA 510(k) and EU MDR"
        self.predicate_devices = self._identify_predicate_devices()
        
    def _identify_predicate_devices(self):
        """Identify legally marketed predicate devices"""
        return {
            "primary_predicate": {
                "device_name": "VITEK 2 AST System",
                "manufacturer": "bioMérieux",
                "clearance": "FDA K033085",
                "similarities": [
                    "Antimicrobial susceptibility testing",
                    "Automated result interpretation",
                    "Clinical decision support"
                ],
                "differences": [
                    "Software-only vs hardware system", 
                    "FHIR integration capabilities",
                    "Cloud-based deployment option"
                ]
            },
            "secondary_predicates": [
                {
                    "device_name": "MicroScan WalkAway System",
                    "manufacturer": "Beckman Coulter",
                    "clearance": "FDA K012345"
                }
            ]
        }
        
    async def prepare_510k_submission(self):
        """Prepare FDA 510(k) submission package"""
        submission_package = {
            "cover_letter": await self._generate_cover_letter(),
            "510k_summary": await self._generate_510k_summary(),
            "indications_for_use": await self._generate_indications_for_use(),
            "substantial_equivalence": await self._demonstrate_substantial_equivalence(),
            "performance_data": await self._compile_performance_data(),
            "software_documentation": await self._prepare_software_documentation(),
            "cybersecurity_documentation": await self._prepare_cybersecurity_docs(),
            "clinical_validation": await self._compile_clinical_validation(),
            "quality_system_information": await self._prepare_quality_system_info()
        }
        
        return submission_package
        
    async def prepare_eu_mdr_submission(self):
        """Prepare EU MDR technical documentation"""
        technical_documentation = {
            "general_safety_performance": await self._generate_gspr_checklist(),
            "device_description": await self._generate_device_description(),
            "classification_justification": await self._justify_classification(),
            "risk_management": await self._compile_risk_management_docs(),
            "clinical_evaluation": await self._compile_clinical_evaluation(),
            "post_market_surveillance": await self._prepare_pms_plan(),
            "udi_assignment": await self._assign_udi(),
            "eudamed_registration": await self._prepare_eudamed_data()
        }
        
        return technical_documentation
```

### **Task 8: Continuous Compliance Monitoring**

```python
# File: medical_device/compliance_monitoring.py

class ComplianceMonitoringSystem:
    """Continuous monitoring of medical device compliance"""
    
    def __init__(self):
        self.monitoring_framework = self._setup_monitoring_framework()
        
    def _setup_monitoring_framework(self):
        return {
            "quality_metrics": [
                "Design control compliance rate",
                "CAPA closure timeline compliance",
                "Risk management update frequency",
                "Clinical data review completeness"
            ],
            "safety_metrics": [
                "Adverse event reporting timeline",
                "Safety signal detection rate",
                "Corrective action effectiveness",
                "Risk control measure performance"
            ],
            "performance_metrics": [
                "Algorithm accuracy trending",
                "System availability metrics",
                "User satisfaction scores",
                "Clinical outcome indicators"
            ]
        }
        
    async def generate_compliance_dashboard(self):
        """Generate real-time compliance monitoring dashboard"""
        dashboard_data = {
            "iso_13485_compliance": await self._assess_qms_compliance(),
            "iso_14971_compliance": await self._assess_risk_management_compliance(),
            "regulatory_compliance": await self._assess_regulatory_compliance(),
            "clinical_performance": await self._assess_clinical_performance(),
            "post_market_surveillance": await self._assess_pms_compliance()
        }
        
        return dashboard_data
        
    async def _assess_qms_compliance(self):
        """Assess ISO 13485 QMS compliance status"""
        return {
            "document_control": "Compliant",
            "management_responsibility": "Compliant", 
            "resource_management": "Compliant",
            "product_realization": "Minor non-conformity identified",
            "measurement_improvement": "Compliant",
            "overall_status": "Substantially Compliant",
            "next_audit_date": "2025-12-01",
            "capa_items": [
                {
                    "id": "CAPA-001",
                    "description": "Update design validation procedures",
                    "due_date": "2025-10-15",
                    "status": "In Progress"
                }
            ]
        }
```

## 🎯 **Success Criteria & Acceptance**

### **Acceptance Criteria for ISO Implementation:**

1. **ISO 13485 Compliance**
   - ✅ Complete QMS documentation
   - ✅ Design controls implementation
   - ✅ Management review processes
   - ✅ CAPA system operational
   - ✅ Internal audit program established

2. **ISO 14971 Risk Management**
   - ✅ Risk management file complete
   - ✅ All identified risks controlled
   - ✅ Residual risks acceptable
   - ✅ Risk-benefit analysis favorable
   - ✅ Post-production monitoring active

3. **Clinical Validation**
   - ✅ Clinical evaluation report complete
   - ✅ Performance criteria met (≥95% concordance)
   - ✅ Safety profile acceptable
   - ✅ User acceptance demonstrated
   - ✅ Clinical utility established

4. **Regulatory Readiness**
   - ✅ Submission packages complete
   - ✅ Predicate device comparison documented
   - ✅ Substantial equivalence demonstrated
   - ✅ Technical documentation compliant
   - ✅ Quality system certification obtained

## 📊 **Implementation Timeline**

### **Phase 1: Foundation Setup (Weeks 1-8)**
- Week 1-2: QMS framework implementation
- Week 3-4: Risk management system setup
- Week 5-6: Design controls establishment
- Week 7-8: Documentation systems deployment

### **Phase 2: Risk Analysis & Control (Weeks 9-16)**
- Week 9-10: Comprehensive hazard analysis
- Week 11-12: Risk control implementation
- Week 13-14: Residual risk evaluation
- Week 15-16: Risk-benefit analysis completion

### **Phase 3: Clinical Validation (Weeks 17-28)**
- Week 17-20: Clinical study protocol finalization
- Week 21-26: Clinical data collection
- Week 27-28: Clinical evaluation report

### **Phase 4: Regulatory Submission (Weeks 29-32)**
- Week 29-30: Submission package compilation
- Week 31-32: Regulatory submission and review

## 💡 **Claude Implementation Prompt**

**Use this prompt to implement ISO 13485 & ISO 14971 compliance:**

```
Implement comprehensive medical device compliance for an AMR Classification Engine according to ISO 13485 and ISO 14971 standards. 

REQUIREMENTS:
1. Create a complete Quality Management System (QMS) framework
2. Implement design controls with defined gates and reviews  
3. Establish risk management processes with comprehensive hazard analysis
4. Develop clinical evaluation protocols and documentation
5. Prepare regulatory submission packages for FDA 510(k) and EU MDR
6. Set up post-market surveillance and continuous monitoring

DELIVERABLES:
- QMS documentation structure and procedures
- Risk management file with AMR-specific hazards
- Design history file with complete traceability
- Clinical evaluation plan and protocols
- Software verification and validation frameworks
- Regulatory submission preparation tools
- Compliance monitoring dashboards

TECHNICAL SPECIFICATIONS:
- Device Classification: Class IIa / Software Safety Class B
- Standards: ISO 13485:2016, ISO 14971:2019, IEC 62304:2006
- Regulatory Pathways: FDA 510(k), EU MDR 2017/745
- Clinical Requirements: ≥95% concordance, comprehensive safety profile

Create production-ready code with comprehensive documentation, automated compliance checking, and continuous monitoring capabilities.
```

## 🔍 **Validation Checklist**

### **ISO 13485 Validation:**
- [ ] QMS procedures documented and implemented
- [ ] Design controls with defined phases and gates
- [ ] Management review processes established
- [ ] Corrective and preventive action (CAPA) system
- [ ] Internal audit program operational
- [ ] Training and competency management
- [ ] Supplier control and evaluation

### **ISO 14971 Validation:**
- [ ] Risk management plan approved
- [ ] Comprehensive hazard analysis completed
- [ ] Risk evaluation against acceptance criteria
- [ ] Risk control measures implemented and verified
- [ ] Residual risk evaluation documented
- [ ] Risk-benefit analysis completed
- [ ] Post-production information monitoring

### **Clinical Validation:**
- [ ] Clinical evaluation plan approved by ethics committee
- [ ] Study protocol following GCP guidelines
- [ ] Statistical analysis plan with adequate power
- [ ] Data collection and monitoring procedures
- [ ] Safety monitoring and adverse event reporting
- [ ] Clinical study report with conclusions

### **Regulatory Validation:**
- [ ] Regulatory pathway determination
- [ ] Predicate device identification and comparison
- [ ] Substantial equivalence documentation
- [ ] Technical documentation completeness
- [ ] Quality system compliance demonstration
- [ ] Post-market commitments defined

---

*Implementation Guide Version: 1.0*  
*Last Updated: September 9, 2025*  
*Estimated Implementation Effort: 320-400 hours*  
*Regulatory Timeline: 6-12 months post-implementation*