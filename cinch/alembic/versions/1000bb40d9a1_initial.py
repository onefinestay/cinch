"""initial

Revision ID: 1000bb40d9a1
Revises: None
Create Date: 2014-09-01 16:36:26.769166

"""

# revision identifiers, used by Alembic.
revision = '1000bb40d9a1'
down_revision = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('master_sha', sa.String(length=40), nullable=True),
        sa.Column('update_status', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'pull_requests',
        sa.Column('number', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('project_id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('head', sa.String(length=40), nullable=False),
        sa.Column('merge_head', sa.String(length=40), nullable=True),
        sa.Column('owner', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('ahead_of_master', sa.Integer(), nullable=True),
        sa.Column('behind_master', sa.Integer(), nullable=True),
        sa.Column('is_mergeable', sa.Boolean(), nullable=True),
        sa.Column('is_open', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('number', 'project_id')
    )

    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_table(
        'job_projects',
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('job_id', 'project_id')
    )
    op.create_table(
        'builds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('build_number', sa.Integer(), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'build_shas',
        sa.Column('build_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('sha', sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(['build_id'], ['builds.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('build_id', 'project_id')
    )


def downgrade():
    op.drop_table('build_shas')
    op.drop_table('builds')
    op.drop_table('job_projects')
    op.drop_table('jobs')
    op.drop_table('pull_requests')
    op.drop_table('projects')
