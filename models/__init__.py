"""Import all models so SQLAlchemy metadata is complete before create_all()."""

from models.auth import (  # noqa: F401
    LearnerProfile,
    LearnerSkill,
    Location,
    MentorProfile,
    MentorSkill,
    Role,
    Skill,
    User,
    VerificationDocument,
)
from models.connection import (  # noqa: F401
    Conversation,
    LearningRelationship,
    LearningRequest,
    Message,
    Notification,
)
from models.learning import (  # noqa: F401
    LearningPlan,
    LearningProgress,
    MentorProfileAccess,
    Payment,
    PaymentInvoice,
    PaymentTransaction,
    PlatformSetting,
    Subscription,
    Withdrawal,
)
from models.store import (  # noqa: F401
    Cart,
    CartItem,
    Order,
    OrderItem,
    Product,
    ProductCategory,
)
from models.reviews import PremiumPlan, RevenueRecord, Review  # noqa: F401
